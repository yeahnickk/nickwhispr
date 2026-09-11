import logging
import re
import time
from dataclasses import asdict
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QMetaObject, QObject, Qt, QThread, Signal, Slot

from whisprnick import config
from whisprnick.core.active_window import get_foreground_window_info
from whisprnick.core.audio import AudioDeviceError, AudioRecorder, device_display_name
from whisprnick.core.cleanup import CleanupEngine
from whisprnick.core.context import detect_app_context
from whisprnick.core.textutil import (
    apply_backtrack, apply_replacements, apply_spoken_commands, light_clean, tidy_text,
)
from whisprnick.core.transcribe import TranscriptionError, WhisperClient, build_vocab_prompt
from whisprnick.data.database import Database
from whisprnick.data.models import DictationEntry

log = logging.getLogger(__name__)

FILLER_PATTERN = re.compile(
    r"\b(um+|uh+|erm|hmm+|you know|i mean|kind of|sort of|basically|literally)\b",
    re.IGNORECASE,
)


class _WarmupWorker(QObject):
    finished = Signal()

    def __init__(self, cleanup: CleanupEngine):
        super().__init__()
        self._cleanup = cleanup

    def run(self):
        self._cleanup.warm_up()
        self.finished.emit()


class _TranscribeWorker(QObject):
    finished = Signal(str, str, int, str)
    error = Signal(str)

    def __init__(
        self,
        audio_bytes: bytes,
        whisper: WhisperClient,
        cleanup: CleanupEngine,
        db_path: str,
        cleanup_level: str,
        cleanup_preset: str,
        source_app: str,
        target_hwnd: int,
        window_title: str = "",
    ):
        super().__init__()
        self._audio_bytes = audio_bytes
        self._whisper = whisper
        self._cleanup = cleanup
        self._db_path = db_path
        self._cleanup_level = cleanup_level
        self._cleanup_preset = cleanup_preset
        self._source_app = source_app
        self._target_hwnd = target_hwnd
        self._window_title = window_title

    def run(self):
        db = None
        try:
            # Own connection: sqlite3 connections are not shared across threads.
            db = Database(self._db_path)
            word_list = [w.word for w in db.get_words()]
            prompt = build_vocab_prompt(word_list)

            try:
                raw_text = self._whisper.transcribe(self._audio_bytes, prompt=prompt)
            except TranscriptionError as e:
                log.error("Transcription failed: %s", e)
                self.error.emit("Transcription failed. See the log")
                return
            if not raw_text:
                self.error.emit("Nothing heard. Try again")
                return

            replacements = {r.trigger: r.replacement for r in db.get_replacements()}
            nicknames = {n.spoken: n.full_name for n in db.get_nicknames()}

            # Resolve spoken layout commands before the model sees the text so
            # it works with real breaks instead of the words "new line".
            raw_text = apply_spoken_commands(raw_text)

            cleaned_text = raw_text
            latency_ms = 0

            if self._cleanup_level != "none" and self._cleanup_preset != "raw":
                profile = db.get_cleanup_profile(self._cleanup_preset)
                rules = asdict(profile)
                template = rules.pop("prompt_template", "")
                context = detect_app_context(self._source_app, self._window_title)

                cleaned_text, latency_ms = self._cleanup.clean(
                    raw_text,
                    rules,
                    dictionary_words=word_list or None,
                    replacements=replacements or None,
                    template=template,
                    context=context,
                    allowed_extra=set(nicknames.values()),
                )
            else:
                cleaned_text = light_clean(raw_text)

            # Deterministic passes run after the model so they always win.
            cleaned_text = apply_spoken_commands(cleaned_text)
            cleaned_text = apply_backtrack(cleaned_text)
            cleaned_text = apply_replacements(cleaned_text, replacements)
            cleaned_text = apply_replacements(cleaned_text, nicknames)
            cleaned_text = tidy_text(cleaned_text)

            self.finished.emit(raw_text, cleaned_text, latency_ms, self._source_app)

        except Exception:
            log.exception("Transcribe worker failed")
            self.error.emit("Dictation failed. See the log")
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass


class DictationPipeline(QObject):
    state_changed = Signal(str)
    transcript_ready = Signal(str, str)
    error = Signal(str)
    level_update = Signal(float)
    elapsed_update = Signal(float)

    def __init__(self, db: Database, settings: dict = None):
        super().__init__()
        self._db = db
        self._settings = settings or {}

        self._whisper = WhisperClient(
            model=config.WHISPER_MODEL,
            device=config.WHISPER_DEVICE,
            compute_type=config.WHISPER_COMPUTE_TYPE,
        )
        self._cleanup = CleanupEngine(
            base_url=config.OLLAMA_URL,
            model=config.OLLAMA_MODEL,
            timeout=config.OLLAMA_TIMEOUT_SECONDS,
        )
        self._recorder = AudioRecorder(
            max_duration=config.MAX_RECORDING_SECONDS,
            silence_threshold=200.0,
        )

        self._source_app = ""
        self._window_title = ""
        self._target_hwnd = 0
        self._worker: Optional[_TranscribeWorker] = None
        self._thread: Optional[QThread] = None
        self._state = "idle"
        self._silence_cutoff = config.SILENCE_CUTOFF_SECONDS
        self._auto_stop_reason = ""

        self._recorder.on_level = self._on_audio_level
        self._recorder.on_silence = self._on_silence
        self._recorder.on_max_reached = self._on_max_reached

    @property
    def state(self) -> str:
        return self._state

    # ── Input device ───────────────────────────────────────────────────

    def set_input_device(self, index: Optional[int]):
        """None follows the Windows default mic; an int pins a device.
        Takes effect on the next recording."""
        self._recorder.device = index
        log.info("Input device set to %s", device_display_name(index))

    @property
    def input_device(self) -> Optional[int]:
        return self._recorder.device

    # ── State ──────────────────────────────────────────────────────────

    def _set_state(self, state: str):
        self._state = state
        self.state_changed.emit(state)

    def _request_auto_stop(self, reason: str):
        self._auto_stop_reason = reason
        QMetaObject.invokeMethod(self, "_auto_stop", Qt.ConnectionType.QueuedConnection)

    def _on_audio_level(self, rms: float):
        normalized = min(rms / 10000.0, 1.0)
        self.level_update.emit(normalized)
        self.elapsed_update.emit(self._recorder.elapsed_seconds)

    def _on_silence(self, seconds: float):
        # Runs on the audio thread. Two cases:
        #  - user has spoken, then gone quiet for the cutoff -> finish and paste
        #  - nothing at all was heard -> give a longer grace period, then discard
        cutoff = self._silence_cutoff
        if self._recorder.had_speech:
            if seconds >= cutoff:
                self._request_auto_stop("silence")
        else:
            grace = max(cutoff, config.NO_SPEECH_GRACE_SECONDS)
            if seconds >= grace:
                self._request_auto_stop("no_speech")

    def _on_max_reached(self):
        self._request_auto_stop("max_duration")

    @Slot()
    def _auto_stop(self):
        if self._state != "listening":
            return
        reason = self._auto_stop_reason
        self._auto_stop_reason = ""
        if reason == "no_speech":
            log.info("No speech detected, discarding recording")
            self._recorder.stop()
            self._set_state("idle")
            self.error.emit("No speech heard. Cancelled")
        else:
            log.info("Auto-stop (%s), transcribing", reason)
            self.stop_recording()

    def start_recording(self):
        if self._state != "idle":
            return

        window_title, app_name, hwnd = get_foreground_window_info()
        self._source_app = app_name or window_title
        self._window_title = window_title
        self._target_hwnd = hwnd

        self._silence_cutoff = self._db.get_setting(
            "silence_cutoff_seconds", config.SILENCE_CUTOFF_SECONDS
        )
        self._recorder._max_duration = self._db.get_setting(
            "max_recording_seconds", config.MAX_RECORDING_SECONDS
        )
        log.info("Safeguards: max=%ss, silence=%ss", self._recorder._max_duration, self._silence_cutoff)

        try:
            self._recorder.start()
        except AudioDeviceError as e:
            log.error("Microphone unavailable: %s", e)
            self.error.emit("Microphone unavailable")
            self._set_state("idle")
            return
        except Exception:
            log.exception("Failed to start recording")
            self.error.emit("Could not start recording. See the log")
            self._set_state("idle")
            return

        self._warmup_thread = QThread()
        self._warmup_worker = _WarmupWorker(self._cleanup)
        self._warmup_worker.moveToThread(self._warmup_thread)
        self._warmup_thread.started.connect(self._warmup_worker.run)
        self._warmup_worker.finished.connect(self._warmup_thread.quit)
        self._warmup_worker.finished.connect(self._warmup_worker.deleteLater)
        self._warmup_thread.finished.connect(self._warmup_thread.deleteLater)
        self._warmup_thread.start()

        self._set_state("listening")
        log.info("Recording started, target: %s (hwnd=%d)", self._source_app, hwnd)

    @Slot()
    def stop_recording(self):
        if self._state != "listening":
            return

        had_speech = self._recorder.had_speech
        audio_bytes = self._recorder.stop()
        if not audio_bytes:
            self.error.emit("No audio captured. Try again")
            self._set_state("idle")
            return
        if not had_speech:
            # Nothing above the noise floor the whole time: don't even ask
            # Whisper, it would only invent something.
            log.info("No speech energy detected, skipping transcription")
            self.error.emit("Nothing heard. Try again")
            self._set_state("idle")
            return

        self._set_state("processing")

        cleanup_level = self._db.get_setting("cleanup_level", "light")
        cleanup_preset = self._db.get_setting("cleanup_preset", "default")

        self._thread = QThread()
        self._worker = _TranscribeWorker(
            audio_bytes=audio_bytes,
            whisper=self._whisper,
            cleanup=self._cleanup,
            db_path=str(self._db.db_path),
            cleanup_level=cleanup_level,
            cleanup_preset=cleanup_preset,
            source_app=self._source_app,
            target_hwnd=self._target_hwnd,
            window_title=self._window_title,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    def _on_worker_finished(
        self,
        raw_text: str,
        cleaned_text: str,
        latency_ms: int,
        source_app: str,
    ):
        fillers = FILLER_PATTERN.findall(raw_text)
        filler_count = len(fillers)
        fillers_str = ", ".join(f.lower() for f in fillers)

        entry = DictationEntry(
            timestamp=datetime.now(),
            source_app=source_app,
            original_text=raw_text,
            cleaned_text=cleaned_text,
            cleanup_level=self._db.get_setting("cleanup_level", "light"),
            cleanup_preset=self._db.get_setting("cleanup_preset", "default"),
            duration_seconds=self._recorder.elapsed_seconds,
            word_count=len(cleaned_text.split()),
            filler_count=filler_count,
            fillers_found=fillers_str,
            latency_ms=latency_ms,
            cost=0.0,
            whisper_model=config.WHISPER_MODEL,
            cleanup_model=config.OLLAMA_MODEL,
        )
        self._db.save_dictation(entry)

        self.transcript_ready.emit(raw_text, cleaned_text)
        self._set_state("done")

        lowered = cleaned_text.lower()
        for w in self._db.get_words():
            if w.word.lower() in lowered:
                self._db.increment_heard(w.word)

        log.info(
            "Pipeline complete: %d words, %d ms cleanup",
            entry.word_count,
            latency_ms,
        )

    def _on_worker_error(self, message: str):
        self.error.emit(message)
        self._set_state("idle")

    def _cleanup_thread(self):
        self._worker = None
        self._thread = None

    def cancel(self):
        if self._state == "listening":
            self._recorder.stop()
            self._set_state("idle")
            log.info("Recording cancelled")
