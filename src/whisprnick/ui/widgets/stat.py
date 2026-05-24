from __future__ import annotations

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QSizePolicy

from whisprnick.ui.styles.theme import Colors, Fonts
from whisprnick.ui.widgets.card import Card


class Stat(QWidget):
    def __init__(
        self,
        value: str = "0",
        label: str = "",
        sub: str | None = None,
        compact: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        value_size = "22px" if compact else "30px"
        label_size = "11px" if compact else "12px"
        sub_size = "10px" if compact else "11px"

        self._value_lbl = QLabel(value, self)
        self._value_lbl.setWordWrap(True)
        self._value_lbl.setStyleSheet(
            f"font-family: \"{Fonts.SERIF}\"; "
            f"font-size: {value_size}; "
            f"color: {Colors.INK}; "
            f"background: transparent;"
        )
        self._value_lbl.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self._value_lbl)

        self._label_lbl = QLabel(label, self)
        self._label_lbl.setWordWrap(True)
        self._label_lbl.setStyleSheet(
            f"font-size: {label_size}; "
            f"color: {Colors.MUTE}; "
            f"background: transparent;"
        )
        layout.addWidget(self._label_lbl)

        if sub:
            self._sub_lbl = QLabel(sub, self)
            self._sub_lbl.setWordWrap(True)
            self._sub_lbl.setStyleSheet(
                f"font-size: {sub_size}; "
                f"color: {Colors.MUTE_2}; "
                f"background: transparent;"
            )
            layout.addWidget(self._sub_lbl)
        else:
            self._sub_lbl = None

    def set_value(self, value: str):
        self._value_lbl.setText(value)

    def set_label(self, label: str):
        self._label_lbl.setText(label)


class BigStat(Card):
    def __init__(
        self,
        value: str = "0",
        label: str = "",
        sub: str | None = None,
        tone: str | None = None,
        parent=None,
    ):
        super().__init__(padded=True, parent=parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        number_color = Colors.INK
        if tone == "accent":
            self.setStyleSheet(
                f"BigStat {{ background: {Colors.ACCENT_SOFT}; "
                f"border: 1px solid {Colors.RULE}; "
                f"border-radius: 14px; "
                f"padding: 18px; }}"
            )
            number_color = Colors.ACCENT_2

        self._stat = Stat(value=value, label=label, sub=sub, parent=self)
        self._stat._value_lbl.setStyleSheet(
            f"font-family: \"{Fonts.SERIF}\"; "
            f"font-size: 30px; "
            f"color: {number_color}; "
            f"background: transparent;"
        )
        layout.addWidget(self._stat)

    def set_value(self, value: str):
        self._stat.set_value(value)

    def set_label(self, label: str):
        self._stat.set_label(label)
