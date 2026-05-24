from __future__ import annotations

from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt, Signal, QSize, Property
from PySide6.QtGui import QPainter, QColor, QPen

from whisprnick.ui.styles.theme import Colors

_SIZES = {
    "sm": (30, 18),
    "md": (36, 20),
}


class Toggle(QPushButton):
    toggled_signal = Signal(bool)

    def __init__(self, on: bool = False, size: str = "md", parent=None):
        super().__init__(parent)
        dims = _SIZES.get(size, _SIZES["md"])
        self._w, self._h = dims
        self._on = on
        self.setFixedSize(self._w, self._h)
        self.setCheckable(True)
        self.setChecked(on)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent; border: none;")
        self.clicked.connect(self._handle_click)

    def _handle_click(self):
        self._on = not self._on
        self.toggled_signal.emit(self._on)
        self.update()

    @property
    def is_on(self) -> bool:
        return self._on

    @is_on.setter
    def is_on(self, value: bool):
        self._on = value
        self.setChecked(value)
        self.update()

    def sizeHint(self):
        return QSize(self._w, self._h)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        track_color = QColor(Colors.ACCENT) if self._on else QColor("#d6c9b1")
        knob_radius = (self._h - 6) / 2.0
        track_radius = self._h / 2.0

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track_color)
        p.drawRoundedRect(0, 0, self._w, self._h, track_radius, track_radius)

        knob_y = self._h / 2.0
        if self._on:
            knob_x = self._w - knob_radius - 3
        else:
            knob_x = knob_radius + 3

        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(knob_x - knob_radius, knob_y - knob_radius,
                       knob_radius * 2, knob_radius * 2)
        p.end()
