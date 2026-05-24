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
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312

VK_MAP = {
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "escape": 0x1B,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "f13": 0x7C,
}

MODIFIER_MAP = {
    "ctrl": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "alt": MOD_ALT,
}

HOTKEY_ID_TOGGLE = 1


def _parse_combo(combo_str: str) -> tuple[int, int]:
    parts = [p.strip().lower() for p in combo_str.split("+")]
    modifiers = MOD_NOREPEAT
    vk = 0
    for part in parts:
        if part in MODIFIER_MAP:
            modifiers |= MODIFIER_MAP[part]
        elif part in VK_MAP:
            vk = VK_MAP[part]
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
        else:
            log.warning("Unknown key: %s", part)
    return modifiers, vk


class HotkeyListener:
    def __init__(self, key_combo: str = "Ctrl+Shift+Space"):
        self._modifiers, self._vk = _parse_combo(key_combo)
        self._combo_str = key_combo
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None
        self._running = False

        self.on_press: Optional[Callable[[], None]] = None
        self.on_release: Optional[Callable[[], None]] = None

    def _thread_main(self):
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        if not user32.RegisterHotKey(None, HOTKEY_ID_TOGGLE, self._modifiers, self._vk):
            log.error("Failed to register hotkey %s (already in use?)", self._combo_str)
            return

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
        log.info("Hotkey unregistered")

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()
        log.info("Hotkey listener started for %s", self._combo_str)

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._thread_id is not None:
            user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._thread_id = None
        log.info("Hotkey listener stopped")
