"""Application orchestrator — wires hotkey, pipeline, HUD, tray, and window."""

import logging
import sys
import ctypes
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QMessageBox

from whisprnick import config
from whisprnick.config import APP_NAME, APP_VERSION, DEFAULT_HOTKEY
from whisprnick.core.hotkey import HotkeyListener
from whisprnick.core.pipeline import DictationPipeline
from whisprnick.data.database import Database
from whisprnick.ui.hud import FloatingHud
from whisprnick.ui.main_window import MainWindow
from whisprnick.ui.styles.theme import get_stylesheet
from whisprnick.ui.tray import SystemTray

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Thread-safe bridge: HotkeyListener callbacks fire from a Win32 thread.
# Qt signals are thread-safe, so we emit from the callback and connect on
# the main thread side.
# ---------------------------------------------------------------------------

class _HotkeyBridge(QObject):
    """Receives raw callbacks from the hotkey thread and re-emits as Qt signals."""
    pressed = Signal()
    released = Signal()


# ---------------------------------------------------------------------------
# Ollama health check (runs in a QTimer singleShot so it doesn't block startup)
# ---------------------------------------------------------------------------

def _ensure_ollama_running():
    """Start Ollama if it's not already running. Non-blocking."""
    import os
    import shutil
    import subprocess

    try:
        import httpx
        resp = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=2.0)
        if resp.status_code == 200:
            log.info("Ollama already running")
            return
    except Exception:
        pass

    ollama_path = shutil.which("ollama")
    if not ollama_path:
        candidate = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
        if os.path.exists(candidate):
            ollama_path = candidate

    if not ollama_path:
        log.warning("Ollama not found — cannot auto-start")
        return

    log.info("Starting Ollama from %s", ollama_path)
    try:
        subprocess.Popen(
            [ollama_path, "serve"],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        log.exception("Failed to start Ollama")


def _check_ollama_async(callback):
    """Non-blocking Ollama availability probe + model warm-up."""
    from PySide6.QtCore import QThread, Signal as _Sig

    class _Worker(QThread):
        result = _Sig(str, bool)

        def run(self):
            try:
                import httpx
                resp = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=4.0)
                resp.raise_for_status()
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                ready = any(config.OLLAMA_MODEL in m for m in models)
                if ready:
                    try:
                        httpx.post(
                            f"{config.OLLAMA_URL}/api/generate",
                            json={"model": config.OLLAMA_MODEL, "prompt": "hi", "stream": False, "keep_alive": "10m"},
                            timeout=30.0,
                        )
                        log.info("Model %s pre-warmed", config.OLLAMA_MODEL)
                    except Exception:
                        pass
                self.result.emit(config.OLLAMA_MODEL, ready)
            except Exception:
                self.result.emit(config.OLLAMA_MODEL, False)

    worker = _Worker()
    worker.result.connect(callback)
    worker.finished.connect(worker.deleteLater)
    worker.start()
    return worker  # caller must hold a reference


def _preload_whisper_async(callback):
    """Load the Whisper model in a background thread so the UI stays responsive."""
    from PySide6.QtCore import QThread, Signal as _Sig

    class _Worker(QThread):
        status = _Sig(str)
        done = _Sig(bool)

        def run(self):
            try:
                self.status.emit("Loading Whisper model...")
                from whisprnick.core.transcribe import _get_model
                _get_model(config.WHISPER_MODEL, config.WHISPER_DEVICE, config.WHISPER_COMPUTE_TYPE)
                self.status.emit("Ready")
                self.done.emit(True)
            except Exception as e:
                log.exception("Failed to preload Whisper model")
                self.status.emit(f"Model load failed: {e}")
                self.done.emit(False)

    worker = _Worker()
    worker.status.connect(lambda msg: callback("status", msg))
    worker.done.connect(lambda ok: callback("done", ok))
    worker.finished.connect(worker.deleteLater)
    worker.start()
    return worker


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class Application:
    def __init__(self):
        # Tell Windows this is its own app, not pythonw.exe
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.vozi.nickwhispr")

        # ── QApplication ───────────────────────────────────────────────
        self._app = QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._app.setApplicationName(APP_NAME)
        self._app.setOrganizationName("Vozi")
        self._app.setApplicationVersion(APP_VERSION)
        self._app.setStyleSheet(get_stylesheet())
        self._app.setQuitOnLastWindowClosed(False)  # keep running in tray

        # ── Ensure Ollama is running ───────────────────────────────────
        _ensure_ollama_running()

        # ── Database ───────────────────────────────────────────────────
        self._db = Database()

        # ── Pipeline ───────────────────────────────────────────────────
        self._pipeline = DictationPipeline(db=self._db)

        # ── HUD ────────────────────────────────────────────────────────
        self._hud = FloatingHud()

        # ── App icon ───────────────────────────────────────────────────
        from PySide6.QtGui import QIcon
        import os
        if getattr(sys, 'frozen', False):
            _base = sys._MEIPASS
        else:
            _base = os.path.dirname(__file__)
        _ico = os.path.join(_base, "whisprnick", "resources", "nickwhispr.ico") if getattr(sys, 'frozen', False) else os.path.join(_base, "resources", "nickwhispr.ico")
        self._app_icon = QIcon(_ico) if os.path.exists(_ico) else QIcon()
        self._app.setWindowIcon(self._app_icon)

        # ── Main window ────────────────────────────────────────────────
        self._window = MainWindow()
        self._window.setWindowIcon(self._app_icon)

        # ── System tray ────────────────────────────────────────────────
        self._tray = SystemTray(self._app_icon)

        # ── Hotkey listener + thread bridge ────────────────────────────
        self._hotkey = HotkeyListener(key_combo=DEFAULT_HOTKEY)
        self._bridge = _HotkeyBridge()
        self._hotkey.on_press = self._bridge.pressed.emit

        # ── Idle-return timer (returns pipeline to idle after "done") ──
        self._idle_timer = QTimer()
        self._idle_timer.setSingleShot(True)
        self._idle_timer.setInterval(2500)
        self._idle_timer.timeout.connect(self._return_to_idle)

        # ── Hold reference for async workers ───────────────────────────
        self._ollama_worker = None
        self._whisper_worker = None
        self._whisper_ready = False

        # ── Wire everything ────────────────────────────────────────────
        self._connect_hotkey()
        self._connect_pipeline_to_hud()
        self._connect_pipeline_to_window()
        self._connect_pipeline_to_tray()
        self._connect_hud()
        self._connect_tray()
        self._connect_settings()
        self._connect_home_page()
        self._connect_dictionary()

        # ── Load persisted settings into components ────────────────────
        self._load_settings()

    # ==================================================================
    # Wiring helpers
    # ==================================================================

    def _connect_hotkey(self):
        """Hotkey bridge (thread-safe) -> pipeline start/stop."""
        self._bridge.pressed.connect(self._on_hotkey_toggle)

    @Slot()
    def _on_hotkey_toggle(self):
        if self._pipeline.state == "listening":
            self._pipeline.stop_recording()
            return

        if self._pipeline.state != "idle":
            return

        if not self._whisper_ready:
            log.warning("Whisper model still loading, ignoring hotkey")
            return

        self._pipeline.start_recording()

    # ── Pipeline -> HUD ────────────────────────────────────────────────

    def _connect_pipeline_to_hud(self):
        self._pipeline.state_changed.connect(self._on_pipeline_state_for_hud)
        self._pipeline.elapsed_update.connect(self._on_elapsed_for_hud)
        self._pipeline.level_update.connect(self._on_level_for_hud)
        self._pipeline.error.connect(self._on_pipeline_error)

    @Slot(str)
    def _on_pipeline_state_for_hud(self, state: str):
        if state == "listening":
            self._hud.set_state("listening")
            self._hud.show_at_taskbar()
            self._idle_timer.stop()
        elif state == "processing":
            self._hud.set_state("processing")
            self._idle_timer.stop()
        elif state == "done":
            word_count = self._last_word_count()
            self._hud.update_done(self._pipeline._source_app, word_count)
            self._hud.set_state("done")
            self._idle_timer.start()
        elif state == "idle":
            self._hud.set_state("idle")
            self._idle_timer.stop()

    @Slot(float)
    def _on_elapsed_for_hud(self, elapsed: float):
        max_dur = self._pipeline._recorder._max_duration
        self._hud.update_listening(elapsed, max_dur, "")

    @Slot(float)
    def _on_level_for_hud(self, level: float):
        bars = self._hud._bar_heights
        if bars:
            import random
            self._hud._bar_heights = [
                max(0.1, min(1.0, level + random.uniform(-0.15, 0.15)))
                for _ in bars
            ]

    @Slot(str)
    def _on_pipeline_error(self, message: str):
        log.error("Pipeline error: %s", message)
        self._hud.set_state("idle")

    # ── Pipeline -> MainWindow ─────────────────────────────────────────

    def _connect_pipeline_to_window(self):
        self._pipeline.state_changed.connect(self._on_pipeline_state_for_window)
        self._pipeline.transcript_ready.connect(self._on_transcript_ready)
        self._pipeline.elapsed_update.connect(self._on_elapsed_for_window)
        self._pipeline.error.connect(self._on_error_for_window)

    @Slot(str)
    def _on_pipeline_state_for_window(self, state: str):
        self._window.set_recording_state(state)
        home = self._get_home_page()
        if home:
            home.set_recording_state(state)
        if state == "done":
            self._refresh_home_stats()
            self._refresh_recent_dictations()
            self._refresh_insights()

    @Slot(str, str)
    def _on_transcript_ready(self, raw: str, cleaned: str):
        home = self._get_home_page()
        if home:
            home.update_transcript(raw, cleaned)
        self._refresh_history_page()

        from whisprnick.core.injector import inject_text
        try:
            inject_text(cleaned, target_hwnd=self._pipeline._target_hwnd)
        except Exception:
            log.exception("Text injection failed")

    def _refresh_history_page(self):
        history = self._get_page_widget("History")
        if history and hasattr(history, "set_entries"):
            raw_entries = self._db.get_recent_dictations(50)
            from datetime import datetime, date
            entries = []
            for e in raw_entries:
                ts = e.timestamp if isinstance(e.timestamp, datetime) else datetime.now()
                if ts.date() == date.today():
                    group = "Today"
                else:
                    group = ts.strftime("%B %d")
                dur = e.duration_seconds or 0
                mins = int(dur) // 60
                secs = int(dur) % 60
                entries.append({
                    "id": e.id,
                    "group": group,
                    "title": (e.cleaned_text or e.original_text or "")[:60],
                    "body": e.cleaned_text or "",
                    "raw": e.original_text or "",
                    "when": ts.strftime("%I:%M %p"),
                    "target": e.source_app or "Unknown",
                    "dur": f"{mins}:{secs:02d}",
                    "words": e.word_count or 0,
                    "trims": [t.strip() for t in (e.fillers_found or "").split(",") if t.strip()],
                    "whisper_model": e.whisper_model or "",
                    "cleanup_model": e.cleanup_model or "",
                    "latency_ms": e.latency_ms or 0,
                })
            history.set_entries(entries)

    @Slot(float)
    def _on_elapsed_for_window(self, elapsed: float):
        pass

    @Slot(str)
    def _on_error_for_window(self, message: str):
        log.error("Pipeline error for window: %s", message)
        home = self._get_home_page()
        if home:
            home.set_recording_state("idle")
            if hasattr(home, 'update_transcript'):
                home.update_transcript("", f"Error: {message}")

    # ── Pipeline -> Tray ───────────────────────────────────────────────

    def _connect_pipeline_to_tray(self):
        self._pipeline.state_changed.connect(self._on_pipeline_state_for_tray)

    @Slot(str)
    def _on_pipeline_state_for_tray(self, state: str):
        tray_state_map = {
            "idle": "idle",
            "listening": "recording",
            "processing": "processing",
            "done": "idle",
        }
        self._tray.set_state(tray_state_map.get(state, "idle"))

    # ── HUD -> Pipeline ────────────────────────────────────────────────

    def _connect_hud(self):
        self._hud.cancel_requested.connect(self._on_hud_cancel)
        self._hud.extend_requested.connect(self._on_hud_extend)
        self._hud.dismissed.connect(self._on_hud_dismissed)

    @Slot()
    def _on_hud_cancel(self):
        self._pipeline.cancel()

    @Slot()
    def _on_hud_extend(self):
        recorder = self._pipeline._recorder
        recorder._max_duration += 30
        log.info("Recording extended by 30s, new max: %ds", recorder._max_duration)

    @Slot()
    def _on_hud_dismissed(self):
        if self._pipeline.state == "done":
            self._pipeline._set_state("idle")

    # ── Tray ───────────────────────────────────────────────────────────

    def _connect_tray(self):
        self._tray.toggle_window.connect(self._toggle_window)
        self._tray.start_dictation.connect(self._on_tray_dictation)
        self._tray.quit_app.connect(self._quit)

    @Slot()
    def _toggle_window(self):
        if self._window.isVisible():
            self._window.hide()
        else:
            self._window.show()
            self._window.raise_()
            self._window.activateWindow()

    @Slot()
    def _on_tray_dictation(self):
        if self._pipeline.state == "idle":
            self._on_hotkey_toggle()

    @Slot()
    def _quit(self):
        log.info("Application quit requested")
        self._hotkey.stop()
        self._db.close()
        self._app.quit()

    # ── Settings page ──────────────────────────────────────────────────

    def _connect_settings(self):
        settings_page = self._get_settings_page()
        if settings_page is None:
            return
        settings_page.wpm_changed.connect(self._on_wpm_changed)

        cleanup_page = self._get_page_widget("Cleanup")
        if cleanup_page and hasattr(cleanup_page, "profile_changed"):
            cleanup_page.profile_changed.connect(self._on_cleanup_changed)

        safeguards_page = self._get_page_widget("Safeguards")
        if safeguards_page and hasattr(safeguards_page, "settings_changed"):
            safeguards_page.settings_changed.connect(self._on_safeguards_changed)

    def _get_page_widget(self, name: str):
        idx = self._window._pages.get(name)
        if idx is not None:
            return self._window._stack.widget(idx)
        return None

    @Slot(int)
    def _on_wpm_changed(self, wpm: int):
        self._db.set_setting("typing_wpm", wpm)
        log.info("Typing WPM updated to %d", wpm)
        self._refresh_home_stats()
        self._refresh_insights()

    @Slot(dict)
    def _on_cleanup_changed(self, profile: dict):
        from whisprnick.data.models import CleanupProfile
        preset = profile.get("preset", "default")
        behaviors = profile.get("behaviors", {})
        template = profile.get("template", "")
        cp = CleanupProfile(
            preset=preset,
            fillers=behaviors.get("fillers", True),
            grammar=behaviors.get("grammar", True),
            punctuation=behaviors.get("punctuation", True),
            capitalize=behaviors.get("capitalize", True),
            paragraphs=behaviors.get("paragraphs", True),
            formal=behaviors.get("formal", False),
            bullets=behaviors.get("bullets", False),
            profanity=behaviors.get("profanity", False),
            prompt_template=template,
        )
        self._db.save_cleanup_profile(cp)
        self._db.set_setting("cleanup_preset", preset)
        log.info("Cleanup profile '%s' saved", preset)

    @Slot(dict)
    def _on_safeguards_changed(self, settings: dict):
        for key, value in settings.items():
            self._db.set_setting(key, value)
        if "max_recording_seconds" in settings:
            self._pipeline._recorder._max_duration = settings["max_recording_seconds"]
            log.info("Max recording updated to %ss", settings["max_recording_seconds"])
        if "silence_cutoff_seconds" in settings:
            self._pipeline._silence_cutoff = settings["silence_cutoff_seconds"]
            log.info("Silence cutoff updated to %ss", settings["silence_cutoff_seconds"])

    # ── Home page ──────────────────────────────────────────────────────

    def _connect_home_page(self):
        home = self._get_home_page()
        if home is None:
            return
        home.start_recording.connect(self._on_hotkey_toggle)
        home.stop_recording.connect(self._on_hotkey_toggle)
        home.navigate_to.connect(self._on_home_navigate)

    def _connect_dictionary(self):
        dic = self._get_page_widget("Dictionary")
        if dic is None:
            return
        dic.word_added.connect(self._on_dict_add_word)
        dic.word_deleted.connect(self._on_dict_del_word)
        dic.replacement_added.connect(self._on_dict_add_replacement)
        dic.replacement_deleted.connect(self._on_dict_del_replacement)
        dic.nickname_added.connect(self._on_dict_add_nickname)
        dic.nickname_deleted.connect(self._on_dict_del_nickname)
        self._refresh_dictionary()

    def _refresh_dictionary(self):
        dic = self._get_page_widget("Dictionary")
        if dic is None:
            return
        words = self._db.get_words()
        dic.set_words([{"id": w.id, "word": w.word, "pronunciation": w.pronunciation,
                        "heard": w.heard_count, "conf": w.confidence} for w in words])
        repls = self._db.get_replacements()
        dic.set_replacements([{"id": r.id, "from": r.trigger, "to": r.replacement} for r in repls])
        nicks = self._db.get_nicknames()
        dic.set_nicknames([{"id": n.id, "spoken": n.spoken, "full_name": n.full_name} for n in nicks])

    @Slot()
    def _on_dict_add_word(self):
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self._window, "Add Word", "Word:")
        if ok and text.strip():
            from whisprnick.data.models import DictionaryWord
            self._db.add_word(DictionaryWord(word=text.strip()))
            self._refresh_dictionary()

    @Slot(int)
    def _on_dict_del_word(self, idx: int):
        words = self._db.get_words()
        if 0 <= idx < len(words):
            self._db.delete_word(words[idx].id)
            self._refresh_dictionary()

    @Slot()
    def _on_dict_add_replacement(self):
        from PySide6.QtWidgets import QInputDialog
        trigger, ok = QInputDialog.getText(self._window, "Add Replacement", "When I say:")
        if ok and trigger.strip():
            replacement, ok2 = QInputDialog.getText(self._window, "Add Replacement", "Type:")
            if ok2 and replacement.strip():
                from whisprnick.data.models import Replacement
                self._db.add_replacement(Replacement(trigger=trigger.strip(), replacement=replacement.strip()))
                self._refresh_dictionary()

    @Slot(int)
    def _on_dict_del_replacement(self, idx: int):
        repls = self._db.get_replacements()
        if 0 <= idx < len(repls):
            self._db.delete_replacement(repls[idx].id)
            self._refresh_dictionary()

    @Slot()
    def _on_dict_add_nickname(self):
        from PySide6.QtWidgets import QInputDialog
        spoken, ok = QInputDialog.getText(self._window, "Add Nickname", "When I say:")
        if ok and spoken.strip():
            full, ok2 = QInputDialog.getText(self._window, "Add Nickname", "Full name:")
            if ok2 and full.strip():
                from whisprnick.data.models import Nickname
                self._db.add_nickname(Nickname(spoken=spoken.strip(), full_name=full.strip()))
                self._refresh_dictionary()

    @Slot(int)
    def _on_dict_del_nickname(self, idx: int):
        nicks = self._db.get_nicknames()
        if 0 <= idx < len(nicks):
            self._db.delete_nickname(nicks[idx].id)
            self._refresh_dictionary()

    @Slot(str)
    def _on_home_navigate(self, target: str):
        page_map = {
            "history": "History",
            "cleanup": "Cleanup",
            "settings": "Settings",
        }
        page_name = page_map.get(target.lower(), target)
        self._window.set_page(page_name)

    # ==================================================================
    # Helpers
    # ==================================================================

    def _get_home_page(self):
        """Retrieve the HomePage widget from the stacked widget."""
        from whisprnick.ui.pages.home import HomePage
        idx = self._window._pages.get("Home")
        if idx is not None:
            widget = self._window._stack.widget(idx)
            if isinstance(widget, HomePage):
                return widget
        return None

    def _get_settings_page(self):
        """Retrieve the SettingsPage widget from the stacked widget."""
        from whisprnick.ui.pages.settings import SettingsPage
        idx = self._window._pages.get("Settings")
        if idx is not None:
            widget = self._window._stack.widget(idx)
            if isinstance(widget, SettingsPage):
                return widget
        return None

    def _last_word_count(self) -> int:
        """Get word count from the most recent dictation entry."""
        recent = self._db.get_recent_dictations(limit=1)
        if recent:
            return recent[0].word_count
        return 0

    def _refresh_home_stats(self):
        """Refresh the Today stats on the home page."""
        home = self._get_home_page()
        if home is None:
            return
        today_entries = self._db.get_dictations_today()
        total_words = sum(e.word_count for e in today_entries)
        total_duration = sum(e.duration_seconds for e in today_entries)
        wpm = self._db.get_setting("typing_wpm", 40)
        home.update_stats(total_words, total_duration, wpm)

    def _refresh_recent_dictations(self):
        """Refresh the Recent dictations list on the home page."""
        home = self._get_home_page()
        if home is None:
            return
        recent = self._db.get_recent_dictations(limit=3)
        entries = []
        for e in recent:
            dur_m = int(e.duration_seconds) // 60
            dur_s = int(e.duration_seconds) % 60
            preview = e.cleaned_text[:80] if e.cleaned_text else e.original_text[:80]
            ts = e.timestamp
            if ts.date() == __import__("datetime").datetime.now().date():
                when = ts.strftime("%I:%M %p").lstrip("0")
            else:
                when = ts.strftime("%b %d")
            entries.append({
                "id": e.id,
                "title": preview,
                "when": when,
                "target": e.source_app or "Unknown",
                "dur": f"{dur_m}:{dur_s:02d}",
                "words": e.word_count,
            })
        home.set_recent_dictations(entries)

    def _return_to_idle(self):
        """Transition pipeline from 'done' to 'idle' after the display timeout."""
        if self._pipeline.state == "done":
            self._pipeline._set_state("idle")

    def _load_settings(self):
        """Load persisted settings into UI and pipeline."""
        # Load WPM into settings UI
        settings_page = self._get_settings_page()
        if settings_page:
            wpm = self._db.get_setting("typing_wpm", 40)
            settings_page.set_wpm(wpm)

        # Load cleanup profile into UI
        cleanup_page = self._get_page_widget("Cleanup")
        if cleanup_page and hasattr(cleanup_page, "set_profile"):
            preset = self._db.get_setting("cleanup_preset", "default")
            profile = self._db.get_cleanup_profile(preset)
            cleanup_page.set_profile(profile)
            log.info("Loaded cleanup profile: %s (suffix: %s...)", preset, profile.prompt_suffix[:30] if profile.prompt_suffix else "empty")

        # Load safeguard values into pipeline
        max_rec = self._db.get_setting("max_recording_seconds", config.MAX_RECORDING_SECONDS)
        self._pipeline._recorder._max_duration = max_rec
        self._pipeline._silence_cutoff = self._db.get_setting(
            "silence_cutoff_seconds", config.SILENCE_CUTOFF_SECONDS
        )
        log.info("Loaded safeguards: max=%ss, silence=%ss", max_rec, self._pipeline._silence_cutoff)

        # Load safeguard values into UI
        safeguards = self._get_page_widget("Safeguards")
        if safeguards and hasattr(safeguards, "set_settings"):
            from whisprnick.data.models import SafeguardSettings
            safeguards.set_settings(SafeguardSettings(
                max_recording_seconds=max_rec,
                silence_cutoff_seconds=self._pipeline._silence_cutoff,
            ))

        # Initial data refresh
        self._refresh_home_stats()
        self._refresh_recent_dictations()
        self._refresh_history_page()
        self._refresh_insights()

    def _refresh_insights(self):
        insights = self._get_page_widget("Insights")
        if insights is None:
            return
        words = self._db.get_total_words(days=7)
        duration = self._db.get_total_duration(days=7)
        fillers = self._db.get_total_fillers(days=7)
        wpm = self._db.get_setting("typing_wpm", 40)
        time_saved = words / max(wpm, 1)
        insights.update_stats(words, time_saved, fillers)

        daily = self._db.get_daily_activity(days=7)
        daily_map = {d: m for d, m in daily}
        today = datetime.now().date()
        today_weekday = today.weekday()
        monday = today - timedelta(days=today_weekday)
        daily_mins = [
            daily_map.get((monday + timedelta(days=i)).isoformat(), 0.0)
            for i in range(7)
        ]
        insights.update_activity(daily_mins, highlight_index=today_weekday)

        app_usage = self._db.get_app_usage(days=7)
        total_w = sum(c for _, c in app_usage) if app_usage else 1
        app_pcts = [(n, int(c / total_w * 100)) for n, c in app_usage[:5]] if app_usage else []
        insights.update_app_usage(app_pcts)

        top_fillers = self._db.get_top_fillers(days=7, limit=6)
        insights.update_top_fillers(top_fillers)

    def _check_ollama(self):
        """Probe Ollama availability and update sidebar + settings."""
        def on_result(model: str, ready: bool):
            self._window.update_ollama_status(model, ready)
            settings_page = self._get_settings_page()
            if settings_page:
                if ready:
                    settings_page.set_ollama_status(model, True, "~2 GB", "ready")
                else:
                    settings_page.set_ollama_status(model, False, "—", "offline")

        self._ollama_worker = _check_ollama_async(on_result)

    def _preload_whisper(self):
        """Start loading the Whisper model in the background."""
        def on_event(event_type, value):
            if event_type == "status":
                self._window.set_loading_status(value)
            elif event_type == "done":
                self._whisper_ready = bool(value)
                self._window.dismiss_loading()
                log.info("Whisper model preload complete (ready=%s)", value)

        self._whisper_worker = _preload_whisper_async(on_event)

    # ==================================================================
    # Run
    # ==================================================================

    def run(self):
        # Start the global keyboard hook listener
        self._hotkey.start()
        log.info("Hotkey listener started for %s", DEFAULT_HOTKEY)

        # Probe Ollama in the background (non-blocking)
        QTimer.singleShot(500, self._check_ollama)

        # Preload Whisper model in background (shows loading overlay)
        QTimer.singleShot(100, self._preload_whisper)

        # Show window and tray
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()
        self._tray.show()

        # Enter Qt event loop
        exit_code = self._app.exec()

        # Cleanup on exit
        self._hotkey.stop()
        self._db.close()
        log.info("Application exited with code %d", exit_code)
        sys.exit(exit_code)
