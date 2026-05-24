from __future__ import annotations

from PySide6.QtWidgets import QLabel

from whisprnick.ui.styles.theme import Colors, Fonts


class FieldLabel(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text.upper(), parent)
        self.setStyleSheet(
            f"FieldLabel {{ "
            f"font-size: 11px; "
            f"color: {Colors.MUTE}; "
            f"letter-spacing: 0.8px; "
            f"font-weight: 500; "
            f"font-family: \"{Fonts.BODY}\"; "
            f"background: transparent; "
            f"}}"
        )
