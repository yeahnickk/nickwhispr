import ctypes
import ctypes.wintypes
import logging
import threading
from typing import Callable, Optional

log = logging.getLogger(__name__)

user32 = ctypes.windll.user32

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

VK_MAP = {
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "escape": 0x1B, "backspace": 0x08,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "capslock": 0x14, "pause": 0x13, "scrolllock": 0x91, "numlock": 0x90, "printscreen": 0x2C,
    **{f"f{i}": 0x6F + i for i in range(1, 25)},
}

MODIFIER_MAP = {
    "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "alt": MOD_ALT,
    "win": MOD_WIN, "meta": MOD_WIN, "super": MOD_WIN, "cmd": MOD_WIN,
}

_MOD_ORDER = [("ctrl", "Ctrl"), ("alt", "Alt"), ("shift", "Shift"), ("win", "Win")]
_MOD_CANON = {"control": "ctrl", "meta": "win", "super": "win", "cmd": "win"}

HOTKEY_ID_TOGGLE = 1


def _split(combo_str: str) -> list[str]:
    return [p.strip().lower() for p in combo_str.split("+") if p.strip()]


def _parse_combo(combo_str: str) -> tuple[int, int]:
    modifiers = MOD_NOREPEAT
    vk = 0
    for part in _split(combo_str):
        if part in MODIFIER_MAP:
            modifiers |= MODIFIER_MAP[part]
        elif part in VK_MAP:
            vk = VK_MAP[part]
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
        else:
            log.warning("Unknown key: %s", part)
    return modifiers, vk


def validate_combo(combo_str: str) -> Optional[str]:
    """Return an error message, or None if the combo can be registered."""
    parts = _split(combo_str)
    if not parts:
        return "No keys given."
    mods = [p for p in parts if p in MODIFIER_MAP]
    keys = [p for p in parts if p not in MODIFIER_MAP]
    if len(keys) != 1:
        return "Use exactly one non-modifier key."
    key = keys[0]
    if not (key in VK_MAP or (len(key) == 1 and key.isalnum())):
        return f"'{key}' is not a supported key."
    if not mods and not key.startswith("f"):
        return "Add Ctrl, Alt, Shift or Win so ordinary typing doesn't trigger it."
    return None


def normalize_combo(combo_str: str) -> str:
    """Canonical display form, e.g. 'shift+ctrl+space' -> 'Ctrl+Shift+Space'."""
    parts = _split(combo_str)
    mods = {_MOD_CANON.get(p, p) for p in parts if p in MODIFIER_MAP}
    keys = [p for p in parts if p not in MODIFIER_MAP]
    out = [label for name, label in _MOD_ORDER if name in mods]
    for k in keys:
        if k.startswith("f") and k[1:].isdigit():
            out.append(k.upper())
        elif len(k) == 1:
            out.append(k.upper())
        else:
            pretty = {"pageup": "PageUp", "pagedown": "PageDown", "capslock": "CapsLock",
                      "scrolllock": "ScrollLock", "numlock": "NumLock", "printscreen": "PrintScreen"}
            out.append(pretty.get(k, k.capitalize()))
    return "+".join(out)


class HotkeyListener:
    """Registers a global Win32 hotkey on its own message-loop thread."""

    def __init__(self, key_combo: str = "Ctrl+Shift+Space"):
        self._modifiers, self._vk = _parse_combo(key_combo)
        self._combo_str = normalize_combo(key_combo)
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None
        self._running = False
        self._ready = threading.Event()
        self.registered = False
        self.register_error: str = ""

        self.on_press: Optional[Callable[[], None]] = None
        self.on_release: Optional[Callable[[], None]] = None

    @property
    def combo(self) -> str:
        return self._combo_str

    def _thread_main(self):
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        if not user32.RegisterHotKey(None, HOTKEY_ID_TOGGLE, self._modifiers, self._vk):
            err = ctypes.get_last_error() or ctypes.windll.kernel32.GetLastError()
            self.register_error = f"{self._combo_str} is already in use by another app (error {err})"
            self.registered = False
            self._running = False
            self._ready.set()
            log.error("Failed to register hotkey %s", self._combo_str)
            return

        self.registered = True
        self._ready.set()
        log.info("Hotkey registered: %s", self._combo_str)

        msg = ctypes.wintypes.MSG()
        while self._running:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result <= 0:
                break
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID_TOGGLE:
                log.debug("Hotkey triggered: %s", self._combo_str)
                if self.on_press is not None:
                    try:
                        self.on_press()
                    except Exception:
                        log.exception("on_press error")

        user32.UnregisterHotKey(None, HOTKEY_ID_TOGGLE)
        self.registered = False
        log.info("Hotkey unregistered")

    def start(self, timeout: float = 1.0) -> bool:
        """Start listening. Returns True once the hotkey is registered."""
        if self._running:
            return self.registered
        self._running = True
        self._ready.clear()
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()
        self._ready.wait(timeout)
        log.info("Hotkey listener started for %s (registered=%s)", self._combo_str, self.registered)
        return self.registered

    def stop(self):
        if not self._running and self._thread is None:
            return
        self._running = False
        if self._thread_id is not None:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._thread_id = None
        log.info("Hotkey listener stopped")
