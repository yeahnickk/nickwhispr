import ctypes
import ctypes.wintypes
import logging
import os

log = logging.getLogger(__name__)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_APP_NAMES: dict[str, str] = {
    "chrome.exe": "Chrome",
    "msedge.exe": "Edge",
    "Code.exe": "VS Code",
    "OUTLOOK.EXE": "Outlook",
    "slack.exe": "Slack",
    "notion.exe": "Notion",
    "Teams.exe": "Teams",
    "explorer.exe": "Explorer",
    "notepad.exe": "Notepad",
    "WINWORD.EXE": "Word",
    "EXCEL.EXE": "Excel",
    "POWERPNT.EXE": "PowerPoint",
    "firefox.exe": "Firefox",
    "WindowsTerminal.exe": "Terminal",
    "Discord.exe": "Discord",
    "Spotify.exe": "Spotify",
}


def _friendly_name(exe_name: str) -> str:
    if exe_name in _APP_NAMES:
        return _APP_NAMES[exe_name]
    lower = exe_name.lower()
    for key, value in _APP_NAMES.items():
        if key.lower() == lower:
            return value
    name = os.path.splitext(exe_name)[0]
    return name


def get_foreground_window_info() -> tuple[str, str, int]:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ("", "", 0)

    title_buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, title_buf, 512)
    window_title = title_buf.value

    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    exe_name = ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if handle:
        try:
            buf = ctypes.create_unicode_buffer(512)
            size = ctypes.wintypes.DWORD(512)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                full_path = buf.value
                exe_name = os.path.basename(full_path)
        except Exception:
            log.exception("Failed to query process image name")
        finally:
            kernel32.CloseHandle(handle)

    friendly = _friendly_name(exe_name) if exe_name else ""
    return (window_title, friendly, hwnd)
