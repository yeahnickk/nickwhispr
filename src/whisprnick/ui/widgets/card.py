from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QVBoxLayout
from PySide6.QtGui import QColor

from whisprnick.ui.styles.theme import Colors


class Card(QFrame):
    def __init__(self, padded: bool = True, parent=None):
        super().__init__(parent)
        pad = 18 if padded else 0
        self.setStyleSheet(
            f"Card {{ background: {Colors.PAPER_2}; "
            f"border: 1px solid {Colors.RULE}; "
            f"border-radius: 14px; "
            f"padding: {pad}px; }}"
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setOffset(0, 1)
        shadow.setBlurRadius(3)
        shadow.setColor(QColor(40, 30, 15, 10))
        self.setGraphicsEffect(shadow)
