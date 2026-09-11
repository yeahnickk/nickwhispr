"""Put text on the Windows clipboard and paste it into the target window.

The clipboard is driven through Win32 directly (no PowerShell round-trip),
which is faster and keeps non-ASCII characters intact. Whatever text was on
the clipboard before is restored a moment after the paste lands.
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
import subprocess
import threading
import time
from typing import Optional

from whisprnick.core.textutil import for_clipboard

log = logging.getLogger(__name__)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002
ASFW_ANY = -1

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]


# ---------------------------------------------------------------------------
# Clipboard
# ---------------------------------------------------------------------------

def _open_clipboard(retries: int = 15) -> bool:
    """Another app can hold the clipboard for a few ms; retry briefly."""
    for _ in range(retries):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def get_clipboard_text() -> Optional[str]:
    """Current clipboard text, or None if it holds something other than text."""
    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return None
    if not _open_clipboard():
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    except Exception:
        log.exception("Reading clipboard failed")
        return None
    finally:
        user32.CloseClipboard()


def _set_clipboard_win32(text: str) -> bool:
    data = text.encode("utf-16-le") + b"\x00\x00"
    if not _open_clipboard():
        log.warning("Clipboard is locked by another application")
        return False
    try:
        if not user32.EmptyClipboard():
            return False
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            kernel32.GlobalFree(handle)
            return False
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            return False
        return True  # the system now owns the handle
    except Exception:
        log.exception("Setting clipboard failed")
        return False
    finally:
        user32.CloseClipboard()


def _set_clipboard_powershell(text: str) -> bool:
    """Last-resort fallback if the Win32 path fails."""
    try:
        process = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-Command",
             "[Console]::InputEncoding=[Text.Encoding]::UTF8; Set-Clipboard -Value ($input | Out-String).TrimEnd()"],
            stdin=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        process.communicate(input=text.encode("utf-8"), timeout=5)
        return process.returncode == 0
    except Exception:
        log.exception("Set-Clipboard failed")
        return False


def set_clipboard_text(text: str) -> bool:
    return _set_clipboard_win32(text) or _set_clipboard_powershell(text)


# ---------------------------------------------------------------------------
# Keyboard / focus
# ---------------------------------------------------------------------------

def _modifiers_held() -> bool:
    return any(
        user32.GetAsyncKeyState(vk) & 0x8000
        for vk in (VK_SHIFT, VK_MENU, VK_LWIN, VK_RWIN)
    )


def _wait_for_modifiers_released(timeout: float = 1.0):
    """If the user is still holding Shift/Alt/Win from the hotkey, Ctrl+V
    would become Ctrl+Shift+V (which some apps treat differently)."""
    deadline = time.monotonic() + timeout
    while _modifiers_held() and time.monotonic() < deadline:
        time.sleep(0.02)


def _press_ctrl_v():
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def _focus_window(hwnd) -> bool:
    try:
        h = wintypes.HWND(hwnd)
        if not user32.IsWindow(h):
            return False
        if user32.GetForegroundWindow() == hwnd:
            return True
        user32.AllowSetForegroundWindow(ASFW_ANY)
        cur_thread = kernel32.GetCurrentThreadId()
        win_thread = user32.GetWindowThreadProcessId(h, None)
        if cur_thread != win_thread:
            user32.AttachThreadInput(cur_thread, win_thread, True)
        result = user32.SetForegroundWindow(h)
        if cur_thread != win_thread:
            user32.AttachThreadInput(cur_thread, win_thread, False)
        return bool(result)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _restore_clipboard(previous: str, ours: str):
    # Only restore if nothing else has touched the clipboard since we did.
    if get_clipboard_text() == ours:
        if _set_clipboard_win32(previous):
            log.debug("Previous clipboard contents restored")


def inject_text(
    text: str,
    target_hwnd: int = None,
    restore_clipboard: bool = True,
    restore_delay: float = 1.0,
):
    text = for_clipboard(text)
    if not text:
        log.warning("Nothing to paste after tidying")
        return

    previous = get_clipboard_text() if restore_clipboard else None

    if not set_clipboard_text(text):
        log.error("Failed to set clipboard")
        return

    log.info("Clipboard set with %d chars", len(text))

    if not target_hwnd:
        log.info("No target hwnd — text left on clipboard")
        return

    if not _focus_window(target_hwnd):
        log.warning("Could not focus hwnd=%s — text is on clipboard, paste manually", target_hwnd)
        return

    time.sleep(0.15)
    _wait_for_modifiers_released()
    _press_ctrl_v()
    log.info("Pasted %d chars into hwnd=%s", len(text), target_hwnd)

    if previous is not None and previous != text:
        timer = threading.Timer(restore_delay, _restore_clipboard, args=(previous, text))
        timer.daemon = True
        timer.start()
