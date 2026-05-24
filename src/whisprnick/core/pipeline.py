import logging
import re
import time
from dataclasses import asdict
from datetime import datetime

from PySide6.QtCore import QObject, QThread, Signal, Slot

from whisprnick import config
from whisprnick.core.active_window import get_foreground_window_info
from whisprnick.core.audio import AudioRecorder
from whisprnick.core.cleanup import CleanupEngine
from whisprnick.core.injector import inject_text
from whisprnick.core.transcribe import WhisperClient
from whisprnick.data.database import Database
from whisprnick.data.models import DictationEntry

log = logging.getLogger(__name__)

FILLER_PATTERN = re.compile(
    r"\b(um|uh|erm|like|you know|so|basically|actually|literally|right)\b",
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

    def run(self):
        try:
            db = Database(self._db_path)
            words = db.get_words()
            word_list = [w.word for w in words]
            prompt = ", ".join(word_list) if word_list else ""

            raw_text = self._whisper.transcribe(
                self._audio_bytes,
                prompt=prompt,
            )

            if not raw_text:
                self.error.emit("Whisper returned empty transcription")
                return

            cleaned_text = raw_text
            latency_ms = 0

            if self._cleanup_level != "none":
                profile = db.get_cleanup_profile(self._cleanup_preset)
                rules = asdict(profile)
                template = rules.pop("prompt_template", "")

                dict_words = word_list if word_list else None
                replacements_list = db.get_replacements()
                repl_dict = (
                    {r.trigger: r.replacement for r in replacements_list}
                    if replacements_list
                    else None
                )

                cleaned_text, latency_ms = self._cleanup.clean(
                    raw_text,
                    rules,
                    dictionary_words=dict_words,
                    replacements=repl_dict,
                    template=template,
                )

            replacements_list = db.get_replacements()
            for r in replacements_list:
                cleaned_text = cleaned_text.replace(r.trigger, r.replacement)

            nicknames = db.get_nicknames()
            for n in nicknames:
                cleaned_text = re.sub(
                    re.escape(n.spoken),
                    n.full_name,
                    cleaned_text,
                    flags=re.IGNORECASE,
                )

            self.finished.emit(
                raw_text,
                cleaned_text,
                latency_ms,
                self._source_app,
            )

        except Exception as e:
            log.exception("Transcribe worker failed")
            self.error.emit(str(e))


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
        )
        self._recorder = AudioRecorder(
            max_duration=config.MAX_RECORDING_SECONDS,
            silence_threshold=200.0,
        )

        self._source_app = ""
        self._target_hwnd = 0
        self._worker: _TranscribeWorker = None
        self._thread: QThread = None
        self._state = "idle"
        self._silence_cutoff = config.SILENCE_CUTOFF_SECONDS

        self._recorder.on_level = self._on_audio_level
        self._recorder.on_silence = self._on_silence
        self._recorder.on_max_reached = self._on_max_reached

    @property
    def state(self) -> str:
        return self._state

    def _set_state(self, state: str):
        self._state = state
        self.state_changed.emit(state)

    def _on_audio_level(self, rms: float):
        normalized = min(rms / 10000.0, 1.0)
        self.level_update.emit(normalized)
        self.elapsed_update.emit(self._recorder.elapsed_seconds)

    def _on_silence(self, seconds: float):
        cutoff = getattr(self, "_silence_cutoff", config.SILENCE_CUTOFF_SECONDS)
        if seconds >= cutoff and self._recorder.elapsed_seconds > 1.0:
            log.info("Silence cutoff reached (%.1f s >= %s s), discarding", seconds, cutoff)
            self._auto_stop_reason = "silence"
            from PySide6.QtCore import QMetaObject, Qt as _Qt
            QMetaObject.invokeMethod(self, "_auto_stop", _Qt.ConnectionType.QueuedConnection)

    def _on_max_reached(self):
        log.info("Max recording duration reached, stopping")
        self._auto_stop_reason = "max_duration"
        from PySide6.QtCore import QMetaObject, Qt as _Qt
        QMetaObject.invokeMethod(self, "_auto_stop", _Qt.ConnectionType.QueuedConnection)

    @Slot()
    def _auto_stop(self):
        reason = getattr(self, "_auto_stop_reason", "unknown")
        if self._state != "listening":
            return
        if reason == "silence":
            log.info("Silence auto-stop: discarding silent audio")
            self._recorder.stop()
            self._set_state("idle")
        else:
            self.stop_recording()

    def start_recording(self):
        if self._state != "idle":
            return

        window_title, app_name, hwnd = get_foreground_window_info()
        self._source_app = app_name or window_title
        self._target_hwnd = hwnd

        self._silence_cutoff = self._db.get_setting(
            "silence_cutoff_seconds", config.SILENCE_CUTOFF_SECONDS
        )
        self._recorder._max_duration = self._db.get_setting(
            "max_recording_seconds", config.MAX_RECORDING_SECONDS
        )
        log.info("Safeguards: max=%ss, silence=%ss", self._recorder._max_duration, self._silence_cutoff)

        self._warmup_thread = QThread()
        self._warmup_worker = _WarmupWorker(self._cleanup)
        self._warmup_worker.moveToThread(self._warmup_thread)
        self._warmup_thread.started.connect(self._warmup_worker.run)
        self._warmup_worker.finished.connect(self._warmup_thread.quit)
        self._warmup_worker.finished.connect(self._warmup_worker.deleteLater)
        self._warmup_thread.finished.connect(self._warmup_thread.deleteLater)
        self._warmup_thread.start()

        self._recorder.start()
        self._set_state("listening")
        log.info("Recording started, target: %s (hwnd=%d)", self._source_app, hwnd)

    @Slot()
    def stop_recording(self):
        if self._state != "listening":
            return

        audio_bytes = self._recorder.stop()
        if not audio_bytes:
            self.error.emit("No audio captured")
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

        for w in self._db.get_words():
            if w.word.lower() in cleaned_text.lower():
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
