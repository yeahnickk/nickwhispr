import io
import logging
import tempfile
import os

log = logging.getLogger(__name__)

_model_instance = None


def _get_model(model_size: str, device: str, compute_type: str):
    global _model_instance
    if _model_instance is None:
        from faster_whisper import WhisperModel
        log.info("Loading Whisper model '%s' (device=%s, compute=%s)", model_size, device, compute_type)
        _model_instance = WhisperModel(model_size, device=device, compute_type=compute_type)
        log.info("Whisper model loaded")
    return _model_instance


class WhisperClient:
    def __init__(self, model: str = "small", device: str = "auto", compute_type: str = "auto"):
        self._model_size = model
        self._device = device
        self._compute_type = compute_type

    def transcribe(
        self,
        audio_bytes: bytes,
        prompt: str = "",
        language: str = "en",
    ) -> str:
        if not audio_bytes:
            return ""

        tmp_path = None
        try:
            model = _get_model(self._model_size, self._device, self._compute_type)

            fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            with open(tmp_path, "wb") as f:
                f.write(audio_bytes)

            segments, info = model.transcribe(
                tmp_path,
                language=language,
                initial_prompt=prompt or None,
                beam_size=5,
            )

            text = " ".join(seg.text.strip() for seg in segments).strip()

            log.info(
                "Transcription complete: %d chars, %.3f s, language=%s",
                len(text),
                info.duration,
                info.language,
            )
            return text

        except Exception:
            log.exception("Whisper transcription failed")
            return ""
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
