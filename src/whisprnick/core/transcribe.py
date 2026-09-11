"""Whisper transcription with hallucination guards.

Whisper's `initial_prompt` is the right way to bias it toward custom
vocabulary, but the prompt becomes decoder context and on silence or noise
the model happily *repeats the prompt back*. That is where "I said nothing
and it typed my dictionary words" comes from. Defences, in order:

1. Silero VAD strips non-speech before decoding.
2. Each segment is dropped if Whisper itself is unsure: high no_speech_prob
   *together with* a low avg_logprob, or a compression ratio that signals a
   repetition loop. See is_low_confidence for why neither score alone will do.
3. Whatever survives is compared against the prompt: if the transcript is
   essentially made of prompt words, it is discarded as an echo.
4. Known silence hallucinations ("Thank you.", "Thanks for watching") are
   dropped when they make up the whole transcript.
"""

import io
import logging
import os
import re
import tempfile
import wave

import numpy as np

from whisprnick.core.textutil import tidy_text

log = logging.getLogger(__name__)

_model_instance = None

_HALLUCINATIONS = {
    "thank you", "thank you very much", "thanks", "thanks for watching",
    "thank you for watching", "please subscribe", "like and subscribe",
    "subtitles by the amara org community", "the end", "you", "bye", "so",
    "hmm", "oh", "uh", "um", "okay", "ok", "yeah", "yes", "no",
}

# Segment-level confidence gates (values from the Whisper paper's decoding
# heuristics, slightly relaxed for short dictation clips).
#
# no_speech_prob on its own is NOT a reliable silence signal: a vocabulary
# initial_prompt routinely pushes it above 0.8 on a 30 s window of perfectly
# good speech. Whisper's own rule (and faster-whisper's) only treats a segment
# as silence when no_speech_prob is high AND the decoder was also unsure of
# the words (avg_logprob below the floor). Applying no_speech alone used to
# throw away whole sentences and leave only the short tail of a dictation.
NO_SPEECH_MAX = 0.6
AVG_LOGPROB_MIN = -1.2
COMPRESSION_RATIO_MAX = 2.4


def is_low_confidence(no_speech_prob: float, avg_logprob: float, compression_ratio: float) -> bool:
    """Whisper paper rule: silence needs both a high no-speech score and a low
    log-prob; a runaway compression ratio means a repetition loop."""
    if compression_ratio > COMPRESSION_RATIO_MAX:
        return True
    return no_speech_prob > NO_SPEECH_MAX and avg_logprob < AVG_LOGPROB_MIN


class TranscriptionError(RuntimeError):
    """Whisper itself failed (model missing, VAD asset missing, backend error).
    Distinct from "nothing was said" so the UI never blames the microphone."""


def _looks_like_vad_failure(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(k in text for k in ("silero", "vad", "onnx"))


def _get_model(model_size: str, device: str, compute_type: str):
    global _model_instance
    if _model_instance is None:
        from faster_whisper import WhisperModel
        log.info("Loading Whisper model '%s' (device=%s, compute=%s)", model_size, device, compute_type)
        _model_instance = WhisperModel(model_size, device=device, compute_type=compute_type)
        log.info("Whisper model loaded")
    return _model_instance


def _wav_to_float32(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
        channels = wf.getnchannels()
        rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio, rate


def _norm_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def is_hallucination(text: str) -> bool:
    key = " ".join(_norm_words(text))
    return key in _HALLUCINATIONS


def is_prompt_echo(text: str, prompt: str) -> bool:
    """True when the transcript is basically the vocabulary prompt read back."""
    if not text or not prompt:
        return False
    words = _norm_words(text)
    if not words:
        return False
    prompt_words = set(_norm_words(prompt))
    # Ignore glue words when judging; "and", "the" etc. are in every prompt.
    meaningful = [w for w in words if len(w) > 2]
    if not meaningful:
        return False
    hits = sum(1 for w in meaningful if w in prompt_words)
    return hits / len(meaningful) >= 0.6


def build_vocab_prompt(words: list[str]) -> str:
    """Whisper reads the prompt as 'previous transcript'. A short natural
    sentence with the rare terms at the end biases spelling without inviting
    the decoder to recite a bare list."""
    words = [w.strip() for w in words if w and w.strip()]
    if not words:
        return ""
    # Only the last ~224 tokens matter; keep the list compact.
    return "Vocabulary: " + ", ".join(words[-40:]) + "."


class WhisperClient:
    def __init__(self, model: str = "small", device: str = "auto", compute_type: str = "auto"):
        self._model_size = model
        self._device = device
        self._compute_type = compute_type
        self._vad_available = True

    def _decode(self, model, source, prompt: str, language: str, use_vad: bool):
        """Run Whisper and apply the per-segment gates. Returns (kept, info, dropped)."""
        kwargs = dict(
            language=language,
            initial_prompt=prompt or None,
            beam_size=5,
            condition_on_previous_text=False,
            no_speech_threshold=NO_SPEECH_MAX,
            log_prob_threshold=AVG_LOGPROB_MIN,
            compression_ratio_threshold=COMPRESSION_RATIO_MAX,
        )
        if use_vad:
            kwargs["vad_filter"] = True
            kwargs["vad_parameters"] = {"min_silence_duration_ms": 500, "speech_pad_ms": 200}

        segments, info = model.transcribe(source, **kwargs)

        kept: list[str] = []
        dropped = 0
        for seg in segments:
            seg_text = seg.text.strip()
            if not seg_text:
                continue
            if is_low_confidence(seg.no_speech_prob, seg.avg_logprob, seg.compression_ratio):
                dropped += 1
                log.info(
                    "Dropping low-confidence segment (no_speech=%.2f logprob=%.2f ratio=%.2f): %r",
                    seg.no_speech_prob, seg.avg_logprob, seg.compression_ratio, seg_text,
                )
                continue
            if prompt and is_prompt_echo(seg_text, prompt):
                dropped += 1
                log.info("Dropping prompt echo segment: %r", seg_text)
                continue
            kept.append(seg_text)
        return kept, info, dropped

    def transcribe(
        self,
        audio_bytes: bytes,
        prompt: str = "",
        language: str = "en",
    ) -> str:
        """Return the cleaned transcript, or "" when nothing was said.

        Raises TranscriptionError when Whisper could not run at all, so the
        caller can tell "silence" from "broken".
        """
        if not audio_bytes:
            return ""

        tmp_path = None
        try:
            model = _get_model(self._model_size, self._device, self._compute_type)

            audio, rate = _wav_to_float32(audio_bytes)
            source = audio
            if rate != 16000:
                fd, tmp_path = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                with open(tmp_path, "wb") as f:
                    f.write(audio_bytes)
                source = tmp_path

            try:
                kept, info, dropped = self._decode(model, source, prompt, language, self._vad_available)
            except Exception as e:
                if self._vad_available and _looks_like_vad_failure(e):
                    # The Silero VAD asset is missing or onnxruntime is unhappy.
                    # Whisper still works without it; the segment gates and
                    # the had_speech check remain in place.
                    log.warning("VAD unavailable, transcribing without it: %s", e)
                    self._vad_available = False
                    kept, info, dropped = self._decode(model, source, prompt, language, False)
                else:
                    raise

            text = tidy_text(" ".join(kept))

            if text and is_hallucination(text):
                log.info("Dropping likely hallucination: %r", text)
                return ""
            if text and prompt and is_prompt_echo(text, prompt):
                log.info("Dropping prompt echo transcript: %r", text)
                return ""

            log.info(
                "Transcription complete: %d chars, %.3f s, %d segments dropped, language=%s",
                len(text), info.duration, dropped, info.language,
            )
            return text

        except Exception as e:
            log.exception("Whisper transcription failed")
            raise TranscriptionError(f"{type(e).__name__}: {e}") from e
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
