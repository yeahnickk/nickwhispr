"""Input widgets that never react to the mouse wheel.

Inside a scrolling page a plain QComboBox or QSlider grabs wheel events the
moment the pointer passes over it, so scrolling the Settings page could
silently switch the microphone. These variants pass the wheel through to the
scroll area; keyboard and mouse clicks still work as normal.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QSlider


class NoWheelComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        # StrongFocus (not the default WheelFocus) so hovering never focuses it.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        event.ignore()


class NoWheelSlider(QSlider):
    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        event.ignore()
