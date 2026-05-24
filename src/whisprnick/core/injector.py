import ctypes
import ctypes.wintypes
import logging
import subprocess
import time

log = logging.getLogger(__name__)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002
ASFW_ANY = -1


def _set_clipboard(text: str) -> bool:
    try:
        process = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
            stdin=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        process.communicate(input=text.encode("utf-8"))
        return process.returncode == 0
    except Exception:
        log.exception("Set-Clipboard failed")
        return False


def _press_ctrl_v():
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def _focus_window(hwnd) -> bool:
    try:
        h = ctypes.wintypes.HWND(hwnd)
        if not user32.IsWindow(h):
            return False
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


def _sanitize(text: str) -> str:
    return (text
        .replace("‘", "'").replace("’", "'")
        .replace("“", '"').replace("”", '"')
        .replace("–", "--").replace("—", "--")
        .replace("…", "..."))


def inject_text(text: str, target_hwnd: int = None):
    text = _sanitize(text)
    if not _set_clipboard(text):
        log.error("Failed to set clipboard")
        return

    log.info("Clipboard set with %d chars", len(text))

    if target_hwnd:
        if _focus_window(target_hwnd):
            time.sleep(0.2)
            _press_ctrl_v()
            log.info("Pasted %d chars into hwnd=%s", len(text), target_hwnd)
        else:
            log.warning("Could not focus hwnd=%s — text is on clipboard, paste manually", target_hwnd)
    else:
        log.info("No target hwnd — text on clipboard")
