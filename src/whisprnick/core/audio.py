import io
import logging
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

# The MME "Sound Mapper" is the one PortAudio device that follows whatever
# Windows currently calls the default microphone, even if that changes while
# the app is running. Every other entry is pinned to one physical device.
_SOUND_MAPPER = "Microsoft Sound Mapper"


class AudioDeviceError(RuntimeError):
    """Raised when no usable microphone could be opened."""


# ---------------------------------------------------------------------------
# Device discovery
# ---------------------------------------------------------------------------

def _hostapi_index(prefix: str) -> Optional[int]:
    try:
        for i, api in enumerate(sd.query_hostapis()):
            if api["name"].lower().startswith(prefix.lower()):
                return i
    except Exception:
        pass
    return None


def refresh_devices() -> None:
    """Make PortAudio re-scan hardware. It caches the device list at init, so
    a mic plugged in after launch is invisible until this runs."""
    try:
        sd._terminate()
        sd._initialize()
        log.info("Audio device list refreshed")
    except Exception:
        log.exception("Failed to refresh audio devices")


def system_default_input_index() -> Optional[int]:
    """Index of the device that tracks the Windows default mic, or None."""
    mme = _hostapi_index("MME")
    try:
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] <= 0:
                continue
            if mme is not None and d["hostapi"] != mme:
                continue
            if d["name"].startswith(_SOUND_MAPPER):
                return i
    except Exception:
        log.exception("Failed to query audio devices")
    return None


def list_input_devices() -> list[dict]:
    """Selectable microphones as ``[{"index": int, "name": str}, ...]``.

    We expose the MME entries because they resample to 16 kHz reliably. MME
    truncates names to 31 characters, so the full name is borrowed from the
    matching WASAPI entry when one exists.
    """
    try:
        devices = sd.query_devices()
    except Exception:
        log.exception("Failed to query audio devices")
        return []

    mme = _hostapi_index("MME")
    wasapi = _hostapi_index("Windows WASAPI")
    full_names = [
        d["name"] for d in devices
        if wasapi is not None and d["hostapi"] == wasapi and d["max_input_channels"] > 0
    ]

    result: list[dict] = []
    seen: set[str] = set()
    for i, d in enumerate(devices):
        if d["max_input_channels"] <= 0:
            continue
        if mme is not None and d["hostapi"] != mme:
            continue
        name = d["name"]
        if name.startswith(_SOUND_MAPPER):
            continue
        display = next((f for f in full_names if f.startswith(name)), name)
        if display in seen:
            continue
        seen.add(display)
        result.append({"index": i, "name": display})
    return result


def device_display_name(index: Optional[int]) -> str:
    if index is None:
        return "System default"
    try:
        return sd.query_devices(index)["name"]
    except Exception:
        return f"Device {index}"


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------

class AudioRecorder:
    def __init__(
        self,
        max_duration: float = 60.0,
        silence_threshold: float = 50.0,
        device: Optional[int] = None,
    ):
        self._max_duration = max_duration
        self._silence_threshold = silence_threshold

        # None = follow the Windows default mic. An int pins a PortAudio index.
        self.device: Optional[int] = device
        self._active_device: Optional[int] = None

        self._chunks: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._recording = False
        self._had_speech = False
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
    def had_speech(self) -> bool:
        """True once any block has exceeded the silence threshold."""
        return self._had_speech

    @property
    def device_name(self) -> str:
        return device_display_name(self._active_device)

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
        if not self._recording:
            return

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
            self._had_speech = True
            self._silence_start = 0.0

        if self.elapsed_seconds >= self._max_duration:
            if self.on_max_reached is not None:
                try:
                    self.on_max_reached()
                except Exception:
                    pass

    def _open_stream(self) -> sd.InputStream:
        """Open the requested device, falling back to the system default and
        then to PortAudio's own default before giving up."""
        requested = self.device
        candidates: list[Optional[int]] = []
        if requested is not None:
            candidates.append(requested)
        default = system_default_input_index()
        if default is not None and default not in candidates:
            candidates.append(default)
        candidates.append(None)

        last_err: Optional[Exception] = None
        for dev in candidates:
            try:
                stream = sd.InputStream(
                    device=dev,
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype=DTYPE,
                    blocksize=BLOCK_SIZE,
                    callback=self._audio_callback,
                )
            except Exception as e:
                last_err = e
                log.warning("Could not open input device %s: %s", device_display_name(dev), e)
                continue
            if requested is not None and dev != requested:
                log.warning(
                    "Requested input device %s unavailable, using %s instead",
                    device_display_name(requested), device_display_name(dev),
                )
            self._active_device = dev
            return stream

        raise AudioDeviceError(f"No working microphone found ({last_err})")

    def _close_stream(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                log.exception("Error stopping audio stream")
            self._stream = None

    def start(self):
        if self._recording:
            return
        with self._lock:
            self._chunks.clear()
        self._silence_start = 0.0
        self._had_speech = False

        self._stream = self._open_stream()

        # Mark as recording *before* starting so the first callbacks see a
        # fresh start time rather than the previous take's elapsed value.
        self._start_time = time.monotonic()
        self._recording = True
        try:
            self._stream.start()
        except Exception as e:
            self._recording = False
            self._close_stream()
            raise AudioDeviceError(f"Could not start microphone: {e}") from e

        log.info("Recording started on %s", self.device_name)

    def stop(self) -> bytes:
        if not self._recording:
            return b""
        self._last_elapsed = time.monotonic() - self._start_time
        self._recording = False
        self._close_stream()

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
