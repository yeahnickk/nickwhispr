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
        self._icon_name = icon_name
        self._icon_lbl: QLabel | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 8, 3)
        layout.setSpacing(4)

        if icon_name:
            self._icon_lbl = QLabel(self)
            self._icon_lbl.setFixedSize(11, 11)
            self._icon_lbl.setStyleSheet("background: transparent;")
            layout.addWidget(self._icon_lbl)

        self._text_lbl = QLabel(text, self)
        layout.addWidget(self._text_lbl)

        self.setFixedHeight(22)
        self.set_tone(tone)

    def set_tone(self, tone: str):
        """Recolour in place so callers can reuse one pill for status changes."""
        t = _TONES.get(tone, _TONES["default"])
        self._tone = tone
        self._text_lbl.setStyleSheet(
            f"background: transparent; color: {t['color']}; "
            f"font-size: 11px; font-weight: 500; font-family: \"{Fonts.BODY}\";"
        )
        if self._icon_lbl is not None and self._icon_name:
            self._icon_lbl.setPixmap(icon_pixmap(self._icon_name, 11, t["color"]))
        self.setStyleSheet(
            f"Pill {{ background: {t['bg']}; border-radius: 10px; }}"
        )

    def setText(self, text: str):
        self._text_lbl.setText(text)

    def text(self) -> str:
        return self._text_lbl.text()
