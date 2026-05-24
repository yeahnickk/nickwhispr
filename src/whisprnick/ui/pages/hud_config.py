from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QPushButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QLinearGradient

from whisprnick.ui.widgets.card import Card
from whisprnick.ui.widgets.btn import Btn
from whisprnick.ui.widgets.kbd import Kbd
from whisprnick.ui.widgets.field_label import FieldLabel
from whisprnick.ui.widgets.section_title import SectionTitle
from whisprnick.ui.widgets.icons import icon_label
from whisprnick.ui.styles.theme import Colors, Fonts

_STATES = [
    ("idle", "Idle (hidden when not dictating)"),
    ("listening", "Listening — words stream in raw"),
    ("warning", "Approaching cap (10s left)"),
    ("processing", "Polishing with Qwen"),
    ("done", "Pasted — auto-dismiss in 2s"),
]

_BEHAVIORS = [
    "Anchored above your taskbar. Drag to reposition.",
    "Auto-dismisses 2 seconds after paste completes.",
]

_SHORTCUTS = [
    ("Start / stop", ["Ctrl", "Shift", "Space"]),
]


class _StatePill(QPushButton):
    def __init__(self, state_id: str, label: str, active: bool = False, parent=None):
        super().__init__(parent)
        self.state_id = state_id
        self._label = label
        self._active = active
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

    def set_active(self, active: bool):
        self._active = active
        self._apply_style()

    def _apply_style(self):
        if self._active:
            self.setStyleSheet(
                f"_StatePill {{ padding: 8px 12px; border: 1px solid {Colors.INK}; "
                f"border-radius: 999px; background: {Colors.INK}; color: {Colors.PAPER}; "
                f"font-size: 12.5px; font-family: \"{Fonts.BODY}\"; }}"
            )
        else:
            self.setStyleSheet(
                f"_StatePill {{ padding: 8px 12px; border: 1px solid {Colors.RULE}; "
                f"border-radius: 999px; background: {Colors.PAPER_3}; color: {Colors.INK_2}; "
                f"font-size: 12.5px; font-family: \"{Fonts.BODY}\"; }}"
                f"_StatePill:hover {{ background: {Colors.PAPER_2}; }}"
            )

        dot_color = Colors.PAPER if self._active else Colors.MUTE_2
        self.setText(f"  {self._label}")


class _HudPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "listening"
        self.setMinimumHeight(320)
        self.setStyleSheet("background: transparent; border: none;")

    def set_state(self, state: str):
        self._state = state
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor("#2b241c"))
        grad.setColorAt(1, QColor("#1a1612"))
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, 14, 14)

        radial_color = QColor(46, 109, 216, 46)
        p.setBrush(radial_color)
        p.drawEllipse(w // 2 - 300, h - 200, 600, 200)

        cx = w // 2
        cy = h // 2

        if self._state == "idle":
            p.setBrush(QColor(255, 255, 255, 64))
            p.drawEllipse(cx - 9, cy - 9, 18, 18)

        elif self._state == "listening":
            pill_w, pill_h = 360, 44
            px = cx - pill_w // 2
            py = cy - pill_h // 2
            p.setBrush(QColor(255, 255, 255, 20))
            p.setPen(QColor(255, 255, 255, 30))
            p.drawRoundedRect(px, py, pill_w, pill_h, 22, 22)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(Colors.ACCENT))
            p.drawEllipse(px + 6, py + 6, 32, 32)

            p.setBrush(QColor(255, 255, 255, 217))
            bars = [10, 16, 8, 20, 13, 18, 9, 14, 22, 12]
            bar_x = px + 48
            for i, bh in enumerate(bars):
                p.drawRoundedRect(bar_x + i * 5, cy - bh // 2, 2, bh, 1, 1)

            p.setPen(QColor("#f4ecd8"))
            f = p.font()
            f.setFamily(Fonts.MONO)
            f.setPixelSize(12)
            p.setFont(f)
            p.setOpacity(0.75)
            p.drawText(bar_x + 60, cy + 4, "0:34 / 1:00")

            p.setOpacity(0.6)
            f.setFamily(Fonts.BODY)
            f.setPixelSize(12)
            p.setFont(f)
            p.drawText(bar_x + 145, cy + 4, "...show the price comparison")
            p.setOpacity(1.0)

        elif self._state == "warning":
            pill_w, pill_h = 280, 44
            px = cx - pill_w // 2
            py = cy - pill_h // 2
            p.setBrush(QColor("#3a2618"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(px, py, pill_w, pill_h, 22, 22)

            p.setPen(QColor("#f3d1a8"))
            f = p.font()
            f.setFamily(Fonts.BODY)
            f.setPixelSize(13)
            f.setBold(True)
            p.setFont(f)
            p.drawText(px + 18, cy + 5, "Auto-cutoff in 0:10")
            f.setBold(False)
            p.setFont(f)

            p.setPen(Qt.PenStyle.NoPen)
            bar_x = px + 170
            bar_w = 60
            p.setBrush(QColor(243, 209, 168, 50))
            p.drawRoundedRect(bar_x, cy - 1, bar_w, 3, 1.5, 1.5)
            p.setBrush(QColor("#f3a85a"))
            p.drawRoundedRect(bar_x, cy - 1, int(bar_w * 0.85), 3, 1.5, 1.5)

            p.setPen(QColor(243, 209, 168, 100))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(px + pill_w - 42, cy - 10, 32, 20, 10, 10)
            p.setPen(QColor("#f3d1a8"))
            f.setPixelSize(11)
            p.setFont(f)
            p.drawText(px + pill_w - 36, cy + 4, "+30s")

        elif self._state == "processing":
            pill_w, pill_h = 320, 44
            px = cx - pill_w // 2
            py = cy - pill_h // 2
            p.setBrush(QColor(255, 255, 255, 20))
            p.setPen(QColor(255, 255, 255, 30))
            p.drawRoundedRect(px, py, pill_w, pill_h, 22, 22)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(192, 138, 58, 230))
            p.drawEllipse(px + 8, py + 8, 28, 28)

            p.setPen(QColor("#f4ecd8"))
            f = p.font()
            f.setFamily(Fonts.BODY)
            f.setPixelSize(13)
            f.setBold(True)
            p.setFont(f)
            p.drawText(px + 46, cy + 5, "Cleaning with Qwen...")

            f.setBold(False)
            f.setFamily(Fonts.MONO)
            f.setPixelSize(11)
            p.setFont(f)
            p.setOpacity(0.55)
            p.drawText(px + pill_w - 55, cy + 4, "~480ms")
            p.setOpacity(1.0)

        elif self._state == "done":
            pill_w, pill_h = 260, 44
            px = cx - pill_w // 2
            py = cy - pill_h // 2
            p.setBrush(QColor("#1b3a1f"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(px, py, pill_w, pill_h, 22, 22)

            p.setPen(QColor("#d4ecc6"))
            f = p.font()
            f.setFamily(Fonts.BODY)
            f.setPixelSize(13)
            f.setBold(True)
            p.setFont(f)
            p.drawText(px + 18, cy + 5, "Pasted into Notion · 47 words")

            f.setBold(False)
            f.setFamily(Fonts.MONO)
            f.setPixelSize(10)
            p.setFont(f)
            p.setOpacity(0.55)
            p.drawText(px + pill_w - 80, cy + 5, "auto-dismiss 2s")
            p.setOpacity(1.0)

        f = p.font()
        f.setFamily(Fonts.MONO)
        f.setPixelSize(12)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255, 140))
        text = "— preview against your desktop wallpaper —"
        tw = p.fontMetrics().horizontalAdvance(text)
        p.drawText(cx - tw // 2, h - 20, text)

        p.end()


class HudConfigPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_state = "listening"

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(28, 28, 28, 28)
        main_layout.setSpacing(0)

        header = SectionTitle(
            "Floating mic HUD",
            "Always-on-top widget. Tiny by design — it hovers just above your taskbar.",
        )
        main_layout.addWidget(header)

        self._preview = _HudPreview()
        main_layout.addWidget(self._preview)
        main_layout.addSpacing(18)

        state_label = FieldLabel("States")
        main_layout.addWidget(state_label)
        main_layout.addSpacing(10)

        state_scroll = QScrollArea()
        state_scroll.setWidgetResizable(True)
        state_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        state_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        state_scroll.setFixedHeight(50)
        state_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        state_row = QHBoxLayout()
        state_row.setSpacing(8)
        state_row.setContentsMargins(0, 0, 0, 0)
        self._state_pills: list[_StatePill] = []
        for sid, label in _STATES:
            pill = _StatePill(sid, label, active=(sid == self._current_state))
            pill.clicked.connect(lambda checked=False, s=sid: self._on_state_selected(s))
            self._state_pills.append(pill)
            state_row.addWidget(pill)
        state_row.addStretch()

        state_wrap = QWidget()
        state_wrap.setStyleSheet("background: transparent;")
        state_wrap.setLayout(state_row)
        state_scroll.setWidget(state_wrap)
        main_layout.addWidget(state_scroll)
        main_layout.addSpacing(22)

        columns = QHBoxLayout()
        columns.setSpacing(14)

        # Behaviour card
        behav_card = Card(padded=True)
        bc_lay = QVBoxLayout(behav_card)
        bc_lay.setContentsMargins(0, 0, 0, 0)
        bc_lay.setSpacing(10)

        bc_title = FieldLabel("Behaviour")
        bc_lay.addWidget(bc_title)

        bullet_list = QLabel(self)
        bullet_html = "<ul style='padding-left: 18px; margin: 0;'>"
        for b in _BEHAVIORS:
            bullet_html += f"<li style='margin-bottom: 6px;'>{b}</li>"
        bullet_html += "</ul>"
        bullet_list.setText(bullet_html)
        bullet_list.setWordWrap(True)
        bullet_list.setStyleSheet(
            f"font-size: 13.5px; color: {Colors.INK_2}; line-height: 170%; background: transparent;"
        )
        bc_lay.addWidget(bullet_list)

        columns.addWidget(behav_card, 1)

        # Shortcuts card
        short_card = Card(padded=True)
        sc_lay = QVBoxLayout(short_card)
        sc_lay.setContentsMargins(0, 0, 0, 0)
        sc_lay.setSpacing(10)

        sc_title = FieldLabel("Shortcuts")
        sc_lay.addWidget(sc_title)

        for label, keys in _SHORTCUTS:
            row = QHBoxLayout()
            row.setSpacing(4)
            lbl = QLabel(label, self)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                f"font-size: 13.5px; color: {Colors.INK}; background: transparent;"
            )
            row.addWidget(lbl, 1)
            for k in keys:
                row.addWidget(Kbd(k))
            sc_lay.addLayout(row)

        columns.addWidget(short_card, 1)

        main_layout.addLayout(columns)
        main_layout.addStretch()

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _on_state_selected(self, state_id: str):
        self._current_state = state_id
        for pill in self._state_pills:
            pill.set_active(pill.state_id == state_id)
        self._preview.set_state(state_id)
