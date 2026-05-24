from __future__ import annotations

import time
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QScrollArea, QFrame, QPushButton,
)
from PySide6.QtCore import Qt, Signal, Slot, QThread

from PySide6.QtGui import QPainter, QColor, QLinearGradient

from whisprnick.ui.widgets.card import Card
from whisprnick.ui.widgets.btn import Btn
from whisprnick.ui.widgets.kbd import Kbd
from whisprnick.ui.widgets.field_label import FieldLabel
from whisprnick.ui.widgets.section_title import SectionTitle
from whisprnick.ui.styles.theme import Colors, Fonts
from whisprnick.config import APP_NAME, APP_VERSION, OLLAMA_URL, OLLAMA_MODEL, WHISPER_MODEL

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

_HOTKEYS = [
    ("Start / stop dictation", ["Ctrl", "Shift", "Space"]),
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
    def __init__(self, level_bar: _InputLevelBar, db_label):
        self._bar = level_bar
        self._db_label = db_label
        self._stream = None

    def start(self):
        try:
            import sounddevice as sd
            import numpy as np
            self._np = np

            def callback(indata, frames, time_info, status):
                rms = float(self._np.sqrt(self._np.mean(indata ** 2)))
                db = 20 * self._np.log10(max(rms, 1e-10))
                normalized = max(0.0, min(1.0, (db + 60) / 60))
                from PySide6.QtCore import QMetaObject, Qt as _Qt, Q_ARG
                QMetaObject.invokeMethod(
                    self._bar, "set_level",
                    _Qt.ConnectionType.QueuedConnection,
                    Q_ARG(float, normalized),
                )

            self._stream = sd.InputStream(
                samplerate=16000, channels=1, dtype="float32",
                blocksize=1024, callback=callback,
            )
            self._stream.start()
        except Exception:
            pass

    def stop(self):
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None


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


class _HotkeyRow(QWidget):
    def __init__(self, label: str, keys: list[str], parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(4)

        lbl = QLabel(label, self)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"font-size: 13px; color: {Colors.INK}; background: transparent;"
        )
        layout.addWidget(lbl, 1)

        for k in keys:
            layout.addWidget(Kbd(k))


class SettingsPage(QWidget):
    wpm_changed = Signal(int)

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

        level_title = FieldLabel("Input level")
        ac_lay.addWidget(level_title)

        level_row = QHBoxLayout()
        level_row.setSpacing(10)
        from whisprnick.ui.widgets.icons import icon_label
        mic_icon = icon_label("audio", 14, Colors.MUTE)
        level_row.addWidget(mic_icon)
        self._level_bar = _InputLevelBar()
        level_row.addWidget(self._level_bar, 1)
        self._db_label = QLabel("-12 dB", self)
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

        for i, (label, keys) in enumerate(_HOTKEYS):
            hk_lay.addWidget(_HotkeyRow(label, keys))
            if i < len(_HOTKEYS) - 1:
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background: {Colors.RULE_2};")
                hk_lay.addWidget(sep)

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
            self._status_label.setText(
                f"{model} running locally · {vram} VRAM · last response {latency}"
            )
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

    def _ensure_audio_monitor(self):
        if not hasattr(self, "_audio_monitor"):
            self._audio_monitor = _AudioMonitor(self._level_bar, self._db_label)

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_audio_monitor()
        self._audio_monitor.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, "_audio_monitor"):
            self._audio_monitor.stop()
