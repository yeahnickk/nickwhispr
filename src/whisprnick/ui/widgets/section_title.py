from __future__ import annotations

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt

from whisprnick.ui.styles.theme import Colors, Fonts


class SectionTitle(QWidget):
    def __init__(
        self,
        title: str = "",
        subtitle: str | None = None,
        action_widget: QWidget | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 14)
        outer.setSpacing(0)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel(title, self)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(
            f"font-family: \"{Fonts.SERIF}\"; "
            f"font-size: 28px; "
            f"color: {Colors.INK}; "
            f"letter-spacing: -0.3px; "
            f"background: transparent;"
        )
        top_row.addWidget(title_lbl)
        top_row.addStretch()

        if action_widget is not None:
            top_row.addWidget(action_widget)

        outer.addLayout(top_row)

        if subtitle:
            sub_lbl = QLabel(subtitle, self)
            sub_lbl.setWordWrap(True)
            sub_lbl.setStyleSheet(
                f"font-size: 13px; "
                f"color: {Colors.MUTE}; "
                f"margin-top: 6px; "
                f"background: transparent;"
            )
            outer.addWidget(sub_lbl)
