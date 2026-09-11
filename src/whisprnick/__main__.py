import logging
import logging.handlers

from whisprnick import config


def _setup_logging():
    """Log to %APPDATA%\\WhisprNick\\whisprnick.log unless a runner (e.g.
    run_debug.py) already configured logging."""
    root = logging.getLogger()
    if root.handlers:
        return
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            config.LOG_PATH, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
    except OSError:
        handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    for noisy in ("httpx", "httpcore", "faster_whisper"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_MUTEX_NAME = "Local\\NickWhispr.SingleInstance"


def _already_running() -> bool:
    """Hold a named mutex for the life of the process. A second copy would
    silently lose the global hotkey, so refuse to start it."""
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if not handle:
        return False
    already = kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
    if already:
        kernel32.CloseHandle(handle)
    else:
        globals()["_MUTEX_HANDLE"] = handle  # keep it alive
    return already


def main():
    _setup_logging()
    if _already_running():
        import ctypes
        logging.getLogger(__name__).warning("Another instance is already running; exiting")
        ctypes.windll.user32.MessageBoxW(
            None,
            f"{config.APP_NAME} is already running.\nLook for the microphone icon in the system tray.",
            config.APP_NAME,
            0x40,  # MB_ICONINFORMATION
        )
        return
    from whisprnick.app import Application
    app = Application()
    app.run()


if __name__ == "__main__":
    main()
