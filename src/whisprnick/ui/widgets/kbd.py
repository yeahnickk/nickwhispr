from __future__ import annotations

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt

from whisprnick.ui.styles.theme import Colors, Fonts


class Kbd(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"Kbd {{ "
            f"min-width: 22px; "
            f"height: 22px; "
            f"padding: 0px 6px; "
            f"border: 1px solid {Colors.RULE}; "
            f"border-bottom: 2px solid {Colors.RULE}; "
            f"border-radius: 6px; "
            f"background: {Colors.PAPER_3}; "
            f"font-size: 11px; "
            f"font-family: \"{Fonts.MONO}\"; "
            f"color: {Colors.INK_2}; "
            f"}}"
        )
