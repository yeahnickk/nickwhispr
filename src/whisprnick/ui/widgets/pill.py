from __future__ import annotations

from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout
from PySide6.QtCore import Qt

from whisprnick.ui.styles.theme import Colors, Fonts
from whisprnick.ui.widgets.icons import icon_pixmap

_TONES = {
    "default": {"bg": "rgba(40,30,15,0.05)", "color": Colors.INK_2},
    "accent": {"bg": Colors.ACCENT_SOFT, "color": Colors.ACCENT_2},
    "good": {"bg": "#e7f0e1", "color": Colors.GOOD},
    "warn": {"bg": "#f6ead0", "color": Colors.WARN},
    "bad": {"bg": "#f6dfd6", "color": Colors.BAD},
    "paper": {"bg": Colors.PAPER_3, "color": Colors.INK_2},
}


class Pill(QWidget):
    def __init__(
        self,
        text: str = "",
        tone: str = "default",
        icon_name: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        t = _TONES.get(tone, _TONES["default"])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 8, 3)
        layout.setSpacing(4)

        if icon_name:
            icon_lbl = QLabel(self)
            px = icon_pixmap(icon_name, 11, t["color"])
            icon_lbl.setPixmap(px)
            icon_lbl.setFixedSize(11, 11)
            icon_lbl.setStyleSheet("background: transparent;")
            layout.addWidget(icon_lbl)

        self._text_lbl = QLabel(text, self)
        self._text_lbl.setStyleSheet(
            f"background: transparent; color: {t['color']}; "
            f"font-size: 11px; font-weight: 500; font-family: \"{Fonts.BODY}\";"
        )
        layout.addWidget(self._text_lbl)

        self.setStyleSheet(
            f"Pill {{ background: {t['bg']}; border-radius: 10px; }}"
        )
        self.setFixedHeight(22)

    def setText(self, text: str):
        self._text_lbl.setText(text)

    def text(self) -> str:
        return self._text_lbl.text()
