from __future__ import annotations

import random
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFrame, QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QTimer

from whisprnick.ui.widgets.card import Card
from whisprnick.ui.widgets.btn import Btn
from whisprnick.ui.widgets.pill import Pill
from whisprnick.ui.widgets.field_label import FieldLabel
from whisprnick.ui.widgets.stat import Stat
from whisprnick.ui.widgets.pipeline import PipelineWidget
from whisprnick.ui.widgets.icons import icon_pixmap
from whisprnick.ui.styles.theme import Colors, Fonts
_TIPS = [
    "Tip: press your hotkey to start dictating, and again to stop.",
    'Tip: say "new paragraph" or "new line" to break up your text.',
    "Tip: recording stops on its own after a pause — tune it under Safeguards.",
    "Tip: Qwen runs on your machine — no internet, no bill.",
    "Tip: text gets pasted into whatever window you were in.",
    "Tip: pick a different mic under Settings › Audio. It resets to the system default on launch.",
]

def _greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    return "Good evening"


class _RecentRow(QWidget):
    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"_RecentRow {{ background: {Colors.PAPER_2}; "
            f"border: 1px solid {Colors.RULE}; border-radius: 10px; }} "
            f"_RecentRow:hover {{ background: {Colors.PAPER_3}; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)

        icon_box = QWidget(self)
        icon_box.setFixedSize(28, 28)
        icon_box.setStyleSheet(
            f"background: {Colors.PAPER_3}; border: 1px solid {Colors.RULE}; border-radius: 8px;"
        )
        ic = QLabel(icon_box)
        px = icon_pixmap("mic", 14, Colors.MUTE)
        ic.setPixmap(px)
        ic.setFixedSize(14, 14)
        ic.setStyleSheet("background: transparent; border: none;")
        ic.move(7, 7)
        layout.addWidget(icon_box)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel(entry.get("title", ""), self)
        title_lbl.setStyleSheet(
            f"font-size: 13.5px; color: {Colors.INK}; font-weight: 500; "
            f"background: transparent; border: none;"
        )
        title_lbl.setWordWrap(True)
        text_col.addWidget(title_lbl)

        sub_lbl = QLabel(f"{entry.get('when', '')} · {entry.get('target', '')}", self)
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet(
            f"font-size: 11.5px; color: {Colors.MUTE}; background: transparent; border: none;"
        )
        text_col.addWidget(sub_lbl)
        layout.addLayout(text_col, 1)

        dur_lbl = QLabel(entry.get("dur", "0:00"), self)
        dur_lbl.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(dur_lbl)

        words_lbl = QLabel(f"{entry.get('words', 0)} words", self)
        words_lbl.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(words_lbl)


class HomePage(QWidget):
    navigate_to = Signal(str)
    start_recording = Signal()
    stop_recording = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {Colors.PAPER};")

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        outer_widget = QWidget()
        outer_widget.setStyleSheet("background: transparent;")
        scroll.setWidget(outer_widget)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

        root = QVBoxLayout(outer_widget)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(20)

        pills_row = QHBoxLayout()
        pills_row.setSpacing(6)
        self._ready_pill = Pill("Ready", tone="paper")
        pills_row.addWidget(self._ready_pill)
        self._time_pill = Pill("0m today", tone="default", icon_name="clock")
        pills_row.addWidget(self._time_pill)
        pills_row.addStretch()
        root.addLayout(pills_row)

        self._greeting_lbl = QLabel(self)
        self._greeting_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._greeting_lbl.setWordWrap(True)
        self._greeting_lbl.setStyleSheet("background: transparent;")
        self._hotkey = "Ctrl+Shift+Space"
        self._render_greeting()
        root.addWidget(self._greeting_lbl)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(14)

        stats_card = Card()
        stats_inner = QVBoxLayout(stats_card)
        stats_inner.setContentsMargins(0, 0, 0, 0)
        stats_inner.setSpacing(10)
        stats_label = FieldLabel("Today")
        stats_inner.addWidget(stats_label)
        stats_grid = QGridLayout()
        stats_grid.setSpacing(8)
        stats_grid.setColumnStretch(0, 1)
        stats_grid.setColumnStretch(1, 1)
        self._stat_words = Stat(value="0", label="words", sub="≈ 0 pages", compact=True)
        self._stat_saved = Stat(value="0m", label="saved", sub="vs typing", compact=True)
        self._stat_recorded = Stat(value="0m", label="recorded", compact=True)
        stats_grid.addWidget(self._stat_words, 0, 0)
        stats_grid.addWidget(self._stat_saved, 0, 1)
        stats_grid.addWidget(self._stat_recorded, 1, 0)
        stats_inner.addLayout(stats_grid)
        cards_row.addWidget(stats_card, 1)

        pipeline_card = Card()
        pipe_layout = QVBoxLayout(pipeline_card)
        pipe_layout.setContentsMargins(0, 0, 0, 0)
        pipe_layout.setSpacing(10)
        pipe_label = FieldLabel("Cleanup pipeline")
        pipe_layout.addWidget(pipe_label)
        self._pipeline_widget = PipelineWidget(self)
        pipe_layout.addWidget(self._pipeline_widget)
        pipe_desc = QLabel(self)
        pipe_desc.setTextFormat(Qt.TextFormat.RichText)
        pipe_desc.setWordWrap(True)
        pipe_desc.setStyleSheet(
            f"font-size: 12px; color: {Colors.MUTE}; background: transparent;"
        )
        pipe_desc.setText(
            f'Audio → <b style="color: {Colors.INK_2};">Whisper</b> (local) '
            f'→ <b style="color: {Colors.INK_2};">Qwen</b> (local) → paste.'
        )
        pipe_layout.addWidget(pipe_desc)
        edit_btn = Btn("Edit cleanup rules ›", variant="ghost", size="sm")
        edit_btn.clicked.connect(lambda: self.navigate_to.emit("cleanup"))
        pipe_layout.addWidget(edit_btn, 0, Qt.AlignmentFlag.AlignLeft)
        cards_row.addWidget(pipeline_card, 1)

        tip_card = Card()
        tip_layout = QVBoxLayout(tip_card)
        tip_layout.setContentsMargins(0, 0, 0, 0)
        tip_layout.setSpacing(8)
        tip_label = FieldLabel("Tip")
        tip_layout.addWidget(tip_label)
        self._tip_lbl = QLabel(random.choice(_TIPS), self)
        self._tip_lbl.setWordWrap(True)
        self._tip_lbl.setStyleSheet(
            f"font-size: 13px; color: {Colors.INK_2}; background: transparent;"
        )
        tip_layout.addWidget(self._tip_lbl)
        tip_layout.addStretch()
        cards_row.addWidget(tip_card, 1)

        root.addLayout(cards_row)

        recent_header = QHBoxLayout()
        recent_header.setContentsMargins(0, 0, 0, 0)
        recent_label = FieldLabel("Recent dictations")
        recent_header.addWidget(recent_label)
        recent_header.addStretch()
        see_all_btn = Btn("See all ›", variant="ghost", size="sm")
        see_all_btn.clicked.connect(lambda: self.navigate_to.emit("history"))
        recent_header.addWidget(see_all_btn)
        root.addLayout(recent_header)

        self._recent_layout = QVBoxLayout()
        self._recent_layout.setSpacing(8)
        root.addLayout(self._recent_layout)

        root.addStretch()
        self._recording_state = "idle"
        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.setInterval(6000)
        self._error_timer.timeout.connect(self._clear_error)

    def _render_greeting(self):
        self._greeting_lbl.setText(
            f'<span style="font-family: \'{Fonts.SERIF}\'; font-size: 36px; '
            f'letter-spacing: -0.5px; color: {Colors.INK};">'
            f'{_greeting()}.</span>'
            f'<span style="font-family: \'{Fonts.SERIF}\'; font-size: 36px; '
            f'letter-spacing: -0.5px; color: {Colors.MUTE};"> Press {self._hotkey} to dictate.</span>'
        )

    def set_hotkey(self, combo: str):
        self._hotkey = combo
        self._render_greeting()

    def set_recording_state(self, state: str):
        self._recording_state = state
        if state == "listening":
            self._error_timer.stop()
            self._set_status("Recording...", "accent")
        elif state == "processing":
            self._set_status("Processing...", "warn")
        elif state == "done":
            self._set_status("Pasted", "good")
        elif state == "idle":
            # An error arrives a moment before "idle"; keep it readable.
            if not self._error_timer.isActive():
                self._set_status("Ready", "paper")

    def _set_status(self, text: str, tone: str):
        # Update the pill that is actually in the layout; replacing the
        # object would leave the visible one frozen on "Ready".
        self._ready_pill.setText(text)
        self._ready_pill.set_tone(tone)

    def show_error(self, message: str):
        short = message if len(message) <= 60 else message[:57] + "..."
        self._set_status(short, "bad")
        self._error_timer.start()

    def _clear_error(self):
        if self._recording_state == "idle":
            self._set_status("Ready", "paper")

    def update_transcript(self, raw: str, cleaned: str):
        words = len(cleaned.split())
        self._set_status(f"Pasted · {words} words", "good")

    def update_stats(self, words: int, duration: float, wpm: int = 40):
        pages = words / 300
        self._stat_words.set_value(f"{words:,}")
        self._stat_words._sub_lbl and self._stat_words._sub_lbl.setText(f"≈ {pages:.1f} pages")
        mins = int(duration / 60)
        self._stat_recorded.set_value(f"{mins}m")
        saved_mins = int(words / max(wpm, 1))
        self._stat_saved.set_value(f"{saved_mins}m")
        if self._stat_saved._sub_lbl:
            self._stat_saved._sub_lbl.setText(f"vs {wpm} wpm typing")
        self._time_pill.setText(f"{mins}m today")

    def set_recent_dictations(self, entries: list):
        while self._recent_layout.count():
            item = self._recent_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()

        for entry in entries[:3]:
            row = _RecentRow(entry, self)
            self._recent_layout.addWidget(row)
