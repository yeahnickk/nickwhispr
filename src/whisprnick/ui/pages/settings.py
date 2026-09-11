from __future__ import annotations

import time
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QScrollArea, QFrame, QPushButton, QComboBox,
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QMetaObject, Q_ARG

from PySide6.QtGui import QPainter, QColor, QLinearGradient, QKeyEvent

from whisprnick.ui.widgets.card import Card
from whisprnick.ui.widgets.btn import Btn
from whisprnick.ui.widgets.kbd import Kbd
from whisprnick.ui.widgets.field_label import FieldLabel
from whisprnick.ui.widgets.section_title import SectionTitle
from whisprnick.ui.styles.theme import Colors, Fonts
from whisprnick.config import APP_NAME, APP_VERSION, OLLAMA_URL, OLLAMA_MODEL, WHISPER_MODEL, DEFAULT_HOTKEY
from whisprnick.core.hotkey import normalize_combo, validate_combo

log = logging.getLogger(__name__)


class _OllamaTestWorker(QThread):
    """Runs a quick Ollama generate request off the main thread."""
    finished = Signal(bool, str, int, str, str)  # success, message, response_time_ms, prompt, response_text

    def run(self):
        prompt = "Say hi"
        try:
            import httpx
            start = time.perf_counter()
            resp = httpx.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 20, "temperature": 0.1},
                },
                timeout=15.0,
            )
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            resp.raise_for_status()
            data = resp.json()
            import re
            raw = data.get("response", "").strip()
            response_text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            self.finished.emit(
                True,
                f"{OLLAMA_MODEL} running locally · {elapsed_ms}ms",
                elapsed_ms,
                prompt,
                response_text,
            )
        except Exception as exc:
            self.finished.emit(False, f"Ollama not responding — {exc}", 0, prompt, "")


_NAV_ITEMS = [
    ("general", "General"),
    ("models", "Models"),
    ("audio", "Audio"),
    ("hotkeys", "Hotkeys"),
    ("privacy", "Privacy"),
    ("about", "About"),
]

class _InputLevelBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(6)
        self._level = 0.0

    @Slot(float)
    def set_level(self, level: float):
        self._level = max(0.0, min(1.0, level))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(Colors.RULE_2))
        p.drawRoundedRect(0, 0, self.width(), self.height(), 3, 3)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0, QColor(Colors.GOOD))
        grad.setColorAt(0.8, QColor(Colors.WARN))
        grad.setColorAt(1.0, QColor(Colors.BAD))
        p.setBrush(grad)
        p.setOpacity(0.7)
        w = int(self.width() * self._level)
        p.drawRoundedRect(0, 0, max(w, 4), self.height(), 3, 3)
        p.end()


class _AudioMonitor:
    """Live input meter for the Settings page. Opens the same device the
    recorder will use so what you see is what gets recorded."""

    def __init__(self, level_bar: _InputLevelBar, db_label):
        self._bar = level_bar
        self._db_label = db_label
        self._stream = None
        self.device = None  # None = system default

    def start(self):
        self.stop()
        try:
            import sounddevice as sd
            import numpy as np
            from whisprnick.core.audio import system_default_input_index
            self._np = np

            def callback(indata, frames, time_info, status):
                rms = float(self._np.sqrt(self._np.mean(indata ** 2)))
                db = 20 * self._np.log10(max(rms, 1e-10))
                normalized = max(0.0, min(1.0, (db + 60) / 60))
                QMetaObject.invokeMethod(
                    self._bar, "set_level",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(float, normalized),
                )
                QMetaObject.invokeMethod(
                    self._db_label, "setText",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, f"{max(db, -60):.0f} dB"),
                )

            device = self.device
            if device is None:
                device = system_default_input_index()

            self._stream = sd.InputStream(
                device=device,
                samplerate=16000, channels=1, dtype="float32",
                blocksize=1024, callback=callback,
            )
            self._stream.start()
        except Exception as exc:
            log.warning("Input meter unavailable: %s", exc)
            self._stream = None
            self._bar.set_level(0.0)
            self._db_label.setText("no input")

    def stop(self):
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None


_QT_KEY_NAMES = {
    Qt.Key.Key_Space: "Space", Qt.Key.Key_Return: "Enter", Qt.Key.Key_Enter: "Enter", Qt.Key.Key_Tab: "Tab",
    Qt.Key.Key_Backspace: "Backspace", Qt.Key.Key_Insert: "Insert", Qt.Key.Key_Delete: "Delete",
    Qt.Key.Key_Home: "Home", Qt.Key.Key_End: "End", Qt.Key.Key_PageUp: "PageUp", Qt.Key.Key_PageDown: "PageDown",
    Qt.Key.Key_Up: "Up", Qt.Key.Key_Down: "Down", Qt.Key.Key_Left: "Left", Qt.Key.Key_Right: "Right",
    Qt.Key.Key_CapsLock: "CapsLock", Qt.Key.Key_Pause: "Pause", Qt.Key.Key_ScrollLock: "ScrollLock",
    Qt.Key.Key_Print: "PrintScreen",
}
_QT_MODIFIER_KEYS = {Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_AltGr}


class _HotkeyCapture(QLineEdit):
    """Read-only field that turns the next key chord into a combo string."""
    captured = Signal(str)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Press the new shortcut... (Esc to cancel)")
        self.setStyleSheet(
            f"QLineEdit {{ background: {Colors.PAPER_3}; border: 1px solid {Colors.ACCENT}; "
            f"border-radius: 8px; padding: 7px 10px; font-size: 13px; color: {Colors.INK}; }}"
        )

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.cancelled.emit()
            return
        mods = event.modifiers()
        parts = []
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")
        if mods & Qt.KeyboardModifier.MetaModifier:
            parts.append("Win")
        if key in _QT_MODIFIER_KEYS:
            self.setText("+".join(parts) + "+..." if parts else "...")
            return
        if key in _QT_KEY_NAMES:
            name = _QT_KEY_NAMES[key]
        elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
            name = f"F{key - Qt.Key.Key_F1 + 1}"
        elif 0x30 <= key <= 0x39 or 0x41 <= key <= 0x5A:
            name = chr(key)
        else:
            self.setText("That key isn't supported")
            return
        combo = "+".join(parts + [name])
        self.setText(combo)
        self.captured.emit(combo)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() in _QT_MODIFIER_KEYS and self.text().endswith("..."):
            self.setText("")


class _NavButton(QPushButton):
    def __init__(self, text: str, section_id: str, parent=None):
        super().__init__(text, parent)
        self.section_id = section_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"_NavButton {{ padding: 8px 12px; font-size: 13px; color: {Colors.INK_2}; "
            f"border-radius: 8px; text-decoration: none; background: transparent; "
            f"border: none; text-align: left; font-family: \"{Fonts.BODY}\"; }}"
            f"_NavButton:hover {{ background: {Colors.RULE_2}; }}"
        )


class SettingsPage(QWidget):
    wpm_changed = Signal(int)
    # Emits a PortAudio device index, or None for "follow the system default".
    input_device_changed = Signal(object)
    hotkey_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Left nav ---
        nav_widget = QWidget(self)
        nav_widget.setFixedWidth(180)
        nav_widget.setStyleSheet("background: transparent;")
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(28, 28, 0, 28)
        nav_layout.setSpacing(4)

        self._nav_buttons: list[_NavButton] = []
        for sid, label in _NAV_ITEMS:
            btn = _NavButton(label, sid)
            btn.clicked.connect(lambda checked=False, s=sid: self._scroll_to(s))
            self._nav_buttons.append(btn)
            nav_layout.addWidget(btn)
        nav_layout.addStretch()

        outer.addWidget(nav_widget)

        # --- Scrollable content ---
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(28, 28, 28, 28)
        self._content_layout.setSpacing(18)

        header = SectionTitle("Settings", "Models, hotkeys, audio, all that.")
        self._content_layout.addWidget(header)

        self._section_widgets: dict[str, QWidget] = {}

        # --- General ---
        general_card = Card(padded=True)
        self._section_widgets["general"] = general_card
        gc_lay = QVBoxLayout(general_card)
        gc_lay.setContentsMargins(0, 0, 0, 0)
        gc_lay.setSpacing(10)
        gc_title = FieldLabel("General")
        gc_lay.addWidget(gc_title)

        wpm_row = QHBoxLayout()
        wpm_row.setSpacing(10)
        wpm_label = QLabel("Your typing speed", self)
        wpm_label.setStyleSheet(
            f"font-size: 13px; color: {Colors.INK}; background: transparent;"
        )
        wpm_row.addWidget(wpm_label, 1)
        self._wpm_input = QLineEdit(self)
        self._wpm_input.setText("40")
        self._wpm_input.setFixedWidth(60)
        self._wpm_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wpm_row.addWidget(self._wpm_input)
        wpm_suffix = QLabel("WPM", self)
        wpm_suffix.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 12px; color: {Colors.MUTE}; background: transparent;"
        )
        wpm_row.addWidget(wpm_suffix)
        gc_lay.addLayout(wpm_row)

        wpm_note = QLabel("Used to calculate 'time saved' in insights and home page.", self)
        wpm_note.setWordWrap(True)
        wpm_note.setStyleSheet(
            f"font-size: 11.5px; color: {Colors.MUTE}; background: transparent;"
        )
        gc_lay.addWidget(wpm_note)

        self._wpm_input.editingFinished.connect(self._on_wpm_changed)
        self._content_layout.addWidget(general_card)

        # --- Models: Whisper (local) ---
        whisper_card = Card(padded=True)
        self._section_widgets["models"] = whisper_card
        wc_lay = QVBoxLayout(whisper_card)
        wc_lay.setContentsMargins(0, 0, 0, 0)
        wc_lay.setSpacing(12)

        wc_title = FieldLabel("Transcription — Whisper (local)")
        wc_lay.addWidget(wc_title)

        whisper_status = QWidget(self)
        whisper_status.setStyleSheet(
            f"background: {Colors.PAPER_3}; border: 1px solid {Colors.RULE}; border-radius: 9px;"
        )
        ws_layout = QHBoxLayout(whisper_status)
        ws_layout.setContentsMargins(12, 12, 12, 12)
        ws_layout.setSpacing(10)

        self._whisper_dot = QWidget(self)
        self._whisper_dot.setFixedSize(8, 8)
        self._whisper_dot.setStyleSheet(
            f"background: {Colors.GOOD}; border-radius: 4px; border: none;"
        )
        ws_layout.addWidget(self._whisper_dot)

        self._whisper_label = QLabel(
            f"faster-whisper · {WHISPER_MODEL} model · runs locally", self
        )
        self._whisper_label.setWordWrap(True)
        self._whisper_label.setStyleSheet(
            f"font-size: 12.5px; color: {Colors.INK}; background: transparent; border: none;"
        )
        ws_layout.addWidget(self._whisper_label, 1)
        wc_lay.addWidget(whisper_status)

        whisper_note = QLabel("No API key needed — model runs entirely on your machine.", self)
        whisper_note.setWordWrap(True)
        whisper_note.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11.5px; color: {Colors.MUTE}; "
            f"background: transparent;"
        )
        wc_lay.addWidget(whisper_note)
        self._content_layout.addWidget(whisper_card)

        # --- Models: Qwen ---
        qwen_card = Card(padded=True)
        qc_lay = QVBoxLayout(qwen_card)
        qc_lay.setContentsMargins(0, 0, 0, 0)
        qc_lay.setSpacing(12)

        qc_title = FieldLabel("Cleanup — Qwen (local)")
        qc_lay.addWidget(qc_title)

        status_bar = QWidget(self)
        status_bar.setStyleSheet(
            f"background: {Colors.PAPER_3}; border: 1px solid {Colors.RULE}; border-radius: 9px;"
        )
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(12, 12, 12, 12)
        sb_layout.setSpacing(10)

        self._status_dot = QWidget(self)
        self._status_dot.setFixedSize(8, 8)
        self._status_dot.setStyleSheet(
            f"background: {Colors.GOOD}; border-radius: 4px; border: none;"
        )
        sb_layout.addWidget(self._status_dot)

        self._status_label = QLabel(
            f"{OLLAMA_MODEL} · checking...", self
        )
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(
            f"font-size: 12.5px; color: {Colors.INK}; background: transparent; border: none;"
        )
        sb_layout.addWidget(self._status_label, 1)

        self._test_btn = Btn("Test", variant="soft", size="sm")
        self._test_btn.clicked.connect(self._on_test_ollama)
        sb_layout.addWidget(self._test_btn)

        qc_lay.addWidget(status_bar)

        # Test result detail card (hidden until test is run)
        self._test_result_card = QWidget(self)
        self._test_result_card.setStyleSheet(
            f"background: {Colors.PAPER_3}; border: 1px solid {Colors.RULE}; border-radius: 9px;"
        )
        self._test_result_card.setVisible(False)
        tr_layout = QVBoxLayout(self._test_result_card)
        tr_layout.setContentsMargins(14, 14, 14, 14)
        tr_layout.setSpacing(6)

        self._test_result_label = QLabel("", self)
        self._test_result_label.setWordWrap(True)
        self._test_result_label.setTextFormat(Qt.TextFormat.PlainText)
        self._test_result_label.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 12px; color: {Colors.INK_2}; "
            f"line-height: 170%; background: transparent; border: none;"
        )
        tr_layout.addWidget(self._test_result_label)
        qc_lay.addWidget(self._test_result_card)

        self._content_layout.addWidget(qwen_card)

        # --- Audio ---
        audio_card = Card(padded=True)
        self._section_widgets["audio"] = audio_card
        ac_lay = QVBoxLayout(audio_card)
        ac_lay.setContentsMargins(0, 0, 0, 0)
        ac_lay.setSpacing(12)

        ac_title = FieldLabel("Audio")
        ac_lay.addWidget(ac_title)

        device_title = FieldLabel("Input device")
        ac_lay.addWidget(device_title)

        device_row = QHBoxLayout()
        device_row.setSpacing(10)
        from whisprnick.ui.widgets.scroll_safe import NoWheelComboBox
        self._device_combo = NoWheelComboBox(self)
        self._device_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._device_combo.setStyleSheet(
            f"QComboBox {{ font-size: 13px; color: {Colors.INK}; background: {Colors.PAPER_3}; "
            f"border: 1px solid {Colors.RULE}; border-radius: 8px; padding: 6px 10px; }}"
            f"QComboBox QAbstractItemView {{ background: {Colors.PAPER}; color: {Colors.INK}; "
            f"selection-background-color: {Colors.PAPER_3}; }}"
        )
        device_row.addWidget(self._device_combo, 1)
        self._device_refresh_btn = Btn("Refresh", variant="soft", size="sm")
        self._device_refresh_btn.setToolTip("Re-scan for microphones plugged in since launch")
        device_row.addWidget(self._device_refresh_btn)
        ac_lay.addLayout(device_row)

        device_note = QLabel(
            "Starts on the system default every launch. Pick a specific mic here "
            "to override it for this session.",
            self,
        )
        device_note.setWordWrap(True)
        device_note.setStyleSheet(
            f"font-size: 11.5px; color: {Colors.MUTE}; background: transparent;"
        )
        ac_lay.addWidget(device_note)

        self._populate_devices()
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        self._device_refresh_btn.clicked.connect(self._on_refresh_devices)

        level_title = FieldLabel("Input level")
        ac_lay.addWidget(level_title)

        level_row = QHBoxLayout()
        level_row.setSpacing(10)
        from whisprnick.ui.widgets.icons import icon_label
        mic_icon = icon_label("audio", 14, Colors.MUTE)
        level_row.addWidget(mic_icon)
        self._level_bar = _InputLevelBar()
        level_row.addWidget(self._level_bar, 1)
        self._db_label = QLabel("— dB", self)
        self._db_label.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; background: transparent;"
        )
        level_row.addWidget(self._db_label)
        ac_lay.addLayout(level_row)
        self._content_layout.addWidget(audio_card)

        # --- Hotkeys ---
        hotkey_card = Card(padded=True)
        self._section_widgets["hotkeys"] = hotkey_card
        hk_lay = QVBoxLayout(hotkey_card)
        hk_lay.setContentsMargins(0, 0, 0, 0)
        hk_lay.setSpacing(2)

        hk_title = FieldLabel("Hotkeys")
        hk_lay.addWidget(hk_title)
        hk_lay.addSpacing(10)

        hk_row = QHBoxLayout()
        hk_row.setContentsMargins(0, 6, 0, 6)
        hk_row.setSpacing(4)
        hk_label = QLabel("Start / stop dictation", self)
        hk_label.setStyleSheet(f"font-size: 13px; color: {Colors.INK}; background: transparent;")
        hk_row.addWidget(hk_label, 1)
        self._hotkey_kbd_layout = QHBoxLayout()
        self._hotkey_kbd_layout.setSpacing(4)
        self._hotkey_kbds: list[Kbd] = []
        hk_row.addLayout(self._hotkey_kbd_layout)
        hk_row.addSpacing(10)
        self._hotkey_change_btn = Btn("Change", variant="soft", size="sm")
        self._hotkey_change_btn.clicked.connect(self._begin_hotkey_capture)
        hk_row.addWidget(self._hotkey_change_btn)
        hk_lay.addLayout(hk_row)

        self._hotkey_capture = _HotkeyCapture(self)
        self._hotkey_capture.captured.connect(self._on_hotkey_captured)
        self._hotkey_capture.cancelled.connect(self._end_hotkey_capture)
        self._hotkey_capture.hide()
        hk_lay.addWidget(self._hotkey_capture)

        self._hotkey_note = QLabel(self)
        self._hotkey_note.setWordWrap(True)
        self._set_hotkey_note("Works anywhere on the desktop. Needs at least one modifier key.")
        hk_lay.addWidget(self._hotkey_note)

        self._hotkey = DEFAULT_HOTKEY
        self._render_hotkey()
        self._content_layout.addWidget(hotkey_card)

        # --- Privacy ---
        privacy_card = Card(padded=True)
        self._section_widgets["privacy"] = privacy_card
        pv_lay = QVBoxLayout(privacy_card)
        pv_lay.setContentsMargins(0, 0, 0, 0)
        pv_lay.setSpacing(8)

        pv_title = FieldLabel("Privacy")
        pv_lay.addWidget(pv_title)

        pv_desc = QLabel(
            "Everything runs locally — audio never leaves your machine. "
            "Whisper transcribes on-device, Qwen cleans up on-device. "
            "Transcripts and settings are stored locally in a SQLite database. "
            "No cloud APIs, no data sent anywhere.",
            self,
        )
        pv_desc.setWordWrap(True)
        pv_desc.setStyleSheet(
            f"font-size: 13px; color: {Colors.INK_2}; line-height: 160%; background: transparent;"
        )
        pv_lay.addWidget(pv_desc)
        self._content_layout.addWidget(privacy_card)

        # --- About ---
        about_card = Card(padded=True)
        about_card.setStyleSheet(
            f"Card {{ background: {Colors.PAPER_2}; border: 1px solid {Colors.RULE}; "
            f"border-radius: 14px; padding: 18px; }}"
        )
        self._section_widgets["about"] = about_card
        ab_lay = QHBoxLayout(about_card)
        ab_lay.setContentsMargins(0, 0, 0, 0)
        ab_lay.setSpacing(12)

        ab_info = QVBoxLayout()
        ab_info.setSpacing(4)
        ab_title = QLabel(self)
        ab_title.setWordWrap(True)
        ab_title.setText(
            f'{APP_NAME} <span style="font-family: {Fonts.MONO}; color: {Colors.MUTE};">'
            f'v{APP_VERSION} · build 2026.05.22</span>'
        )
        ab_title.setStyleSheet(
            f"font-size: 14px; color: {Colors.INK}; font-weight: 500; background: transparent;"
        )
        ab_info.addWidget(ab_title)

        ab_sub = QLabel("talk, it types. · 100% local.", self)
        ab_sub.setStyleSheet(
            f"font-size: 12px; color: {Colors.MUTE}; background: transparent;"
        )
        ab_info.addWidget(ab_sub)
        ab_lay.addLayout(ab_info, 1)
        self._content_layout.addWidget(about_card)

        self._content_layout.addStretch()

        self._scroll.setWidget(content)
        outer.addWidget(self._scroll, 1)

    # -- Hotkey ---------------------------------------------------------

    def _set_hotkey_note(self, text: str, error: bool = False):
        color = Colors.BAD if error else Colors.MUTE
        self._hotkey_note.setText(text)
        self._hotkey_note.setStyleSheet(
            f"font-size: 11.5px; color: {color}; background: transparent; padding-top: 6px;"
        )

    def _render_hotkey(self):
        for k in self._hotkey_kbds:
            self._hotkey_kbd_layout.removeWidget(k)
            k.deleteLater()
        self._hotkey_kbds = [Kbd(part) for part in self._hotkey.split("+")]
        for k in self._hotkey_kbds:
            self._hotkey_kbd_layout.addWidget(k)

    def set_hotkey(self, combo: str):
        self._hotkey = normalize_combo(combo)
        self._render_hotkey()
        self._end_hotkey_capture()

    def show_hotkey_error(self, message: str):
        self._set_hotkey_note(message, error=True)

    def _begin_hotkey_capture(self):
        self._hotkey_capture.setText("")
        self._hotkey_capture.show()
        self._hotkey_capture.setFocus()
        self._hotkey_change_btn.setEnabled(False)
        self._set_hotkey_note("Hold the modifiers, then press the key.")

    def _end_hotkey_capture(self):
        self._hotkey_capture.hide()
        self._hotkey_change_btn.setEnabled(True)

    def _on_hotkey_captured(self, combo: str):
        err = validate_combo(combo)
        if err:
            self.show_hotkey_error(err)
            self._hotkey_capture.setText("")
            return
        self._set_hotkey_note("Works anywhere on the desktop. Needs at least one modifier key.")
        self.hotkey_changed.emit(normalize_combo(combo))

    def _scroll_to(self, section_id: str):
        widget = self._section_widgets.get(section_id)
        if widget:
            self._scroll.ensureWidgetVisible(widget, 0, 50)

    def set_ollama_status(self, model: str, ready: bool, vram: str, latency: str):
        color = Colors.GOOD if ready else Colors.BAD
        self._status_dot.setStyleSheet(
            f"background: {color}; border-radius: 4px; border: none;"
        )
        if ready:
            self._status_label.setText(f"{model} running locally · {vram} on disk")
        else:
            self._status_label.setText(f"{model} not running")

    def _on_test_ollama(self):
        self._test_btn.setEnabled(False)
        self._status_label.setText("Testing...")
        self._status_dot.setStyleSheet(
            f"background: {Colors.MUTE}; border-radius: 4px; border: none;"
        )

        self._ollama_worker = _OllamaTestWorker()
        self._ollama_worker.finished.connect(self._on_test_result)
        self._ollama_worker.start()

    def _on_test_result(self, success: bool, message: str, ms: int, prompt: str, response_text: str):
        color = Colors.GOOD if success else Colors.BAD
        self._status_dot.setStyleSheet(
            f"background: {color}; border-radius: 4px; border: none;"
        )
        self._status_label.setText(message)
        self._test_btn.setEnabled(True)

        if success:
            status_line = f"Connected"
            detail = (
                f"Input:   {prompt}\n"
                f"Output:  {response_text}\n"
                f"Latency: {ms}ms\n"
                f"Status:  {status_line}"
            )
        else:
            detail = (
                f"Input:   {prompt}\n"
                f"Output:  —\n"
                f"Latency: —\n"
                f"Status:  Failed: {message}"
            )
        self._test_result_label.setText(detail)
        self._test_result_card.setVisible(True)

    def _on_wpm_changed(self):
        try:
            wpm = int(self._wpm_input.text())
            if wpm > 0:
                self.wpm_changed.emit(wpm)
        except ValueError:
            pass

    def set_wpm(self, wpm: int):
        self._wpm_input.setText(str(wpm))

    # ── Input device ───────────────────────────────────────────────────

    def _populate_devices(self, keep_index=None):
        """Fill the combo. ``keep_index`` re-selects a device after a refresh."""
        from whisprnick.core.audio import list_input_devices

        self._device_combo.blockSignals(True)
        self._device_combo.clear()
        self._device_combo.addItem("System default", None)
        selected_row = 0
        for row, dev in enumerate(list_input_devices(), start=1):
            self._device_combo.addItem(dev["name"], dev["index"])
            if keep_index is not None and dev["index"] == keep_index:
                selected_row = row
        self._device_combo.setCurrentIndex(selected_row)
        self._device_combo.blockSignals(False)

    def current_input_device(self):
        return self._device_combo.currentData()

    @Slot(int)
    def _on_device_changed(self, _row: int):
        device = self.current_input_device()
        log.info("Input device selected: %s", self._device_combo.currentText())
        self.input_device_changed.emit(device)
        if hasattr(self, "_audio_monitor"):
            self._audio_monitor.device = device
            if self.isVisible():
                self._audio_monitor.start()

    @Slot()
    def _on_refresh_devices(self):
        from whisprnick.core.audio import refresh_devices

        previous_name = self._device_combo.currentText()
        if hasattr(self, "_audio_monitor"):
            self._audio_monitor.stop()
        refresh_devices()  # indices can change, so match by name afterwards
        self._populate_devices()
        row = self._device_combo.findText(previous_name)
        if row < 0:
            row = 0
        self._device_combo.blockSignals(True)
        self._device_combo.setCurrentIndex(row)
        self._device_combo.blockSignals(False)
        self._on_device_changed(row)

    def _ensure_audio_monitor(self):
        if not hasattr(self, "_audio_monitor"):
            self._audio_monitor = _AudioMonitor(self._level_bar, self._db_label)
            self._audio_monitor.device = self.current_input_device()

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_audio_monitor()
        self._audio_monitor.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, "_audio_monitor"):
            self._audio_monitor.stop()
