import io
import logging
import struct
import threading
import time
import wave
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
BLOCK_SIZE = 1024


class AudioRecorder:
    def __init__(
        self,
        max_duration: float = 60.0,
        silence_threshold: float = 50.0,
    ):
        self._max_duration = max_duration
        self._silence_threshold = silence_threshold

        self._chunks: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._recording = False
        self._start_time: float = 0.0
        self._last_elapsed: float = 0.0
        self._silence_start: float = 0.0
        self._lock = threading.Lock()

        self.on_level: Optional[Callable[[float], None]] = None
        self.on_silence: Optional[Callable[[float], None]] = None
        self.on_max_reached: Optional[Callable[[], None]] = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def elapsed_seconds(self) -> float:
        if not self._recording:
            return self._last_elapsed
        return time.monotonic() - self._start_time

    @property
    def silence_seconds(self) -> float:
        if not self._recording or self._silence_start == 0.0:
            return 0.0
        return time.monotonic() - self._silence_start

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        if status:
            log.warning("Audio stream status: %s", status)

        chunk = indata[:, 0].copy()
        with self._lock:
            self._chunks.append(chunk)

        rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))

        if self.on_level is not None:
            try:
                self.on_level(rms)
            except Exception:
                pass

        now = time.monotonic()
        if rms < self._silence_threshold:
            if self._silence_start == 0.0:
                self._silence_start = now
            silence_dur = now - self._silence_start
            if self.on_silence is not None:
                try:
                    self.on_silence(silence_dur)
                except Exception:
                    pass
        else:
            self._silence_start = 0.0

        if self.elapsed_seconds >= self._max_duration:
            if self.on_max_reached is not None:
                try:
                    self.on_max_reached()
                except Exception:
                    pass

    def start(self):
        if self._recording:
            return
        with self._lock:
            self._chunks.clear()
        self._silence_start = 0.0
        self._start_time = time.monotonic()
        self._recording = True

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=BLOCK_SIZE,
            callback=self._audio_callback,
        )
        self._stream.start()
        log.info("Recording started")

    def stop(self) -> bytes:
        if not self._recording:
            return b""
        self._last_elapsed = time.monotonic() - self._start_time
        self._recording = False

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                log.exception("Error stopping audio stream")
            self._stream = None

        with self._lock:
            if not self._chunks:
                return b""
            audio_data = np.concatenate(self._chunks)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())

        log.info("Recording stopped, %d samples captured", len(audio_data))
        return buf.getvalue()
