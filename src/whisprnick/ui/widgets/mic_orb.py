from __future__ import annotations

import math
import random

from PySide6.QtWidgets import QPushButton, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QSize, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

from whisprnick.ui.styles.theme import Colors
from whisprnick.ui.widgets.icons import icon_pixmap

_SIZE = 96


class MicOrb(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(_SIZE, _SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent; border: none;")

        self._state = "idle"
        self._bar_heights = [0.3, 0.5, 0.8, 0.5, 0.3]
        self._bar_timer = QTimer(self)
        self._bar_timer.setInterval(80)
        self._bar_timer.timeout.connect(self._animate_bars)

        self._shadow = QGraphicsDropShadowEffect(self)
        self._apply_shadow()
        self.setGraphicsEffect(self._shadow)

    def set_state(self, state: str):
        if state == self._state:
            return
        self._state = state
        if state == "listening":
            self._bar_timer.start()
        else:
            self._bar_timer.stop()
        self._apply_shadow()
        self.update()

    def _apply_shadow(self):
        self._shadow.setOffset(0, 2)
        if self._state == "idle":
            self._shadow.setBlurRadius(8)
            self._shadow.setColor(QColor(40, 30, 15, 30))
        elif self._state == "listening":
            self._shadow.setBlurRadius(24)
            self._shadow.setColor(QColor(46, 109, 216, 100))
        elif self._state == "processing":
            self._shadow.setBlurRadius(20)
            self._shadow.setColor(QColor(192, 138, 58, 90))

    def _animate_bars(self):
        self._bar_heights = [
            max(0.15, min(1.0, h + random.uniform(-0.3, 0.3)))
            for h in self._bar_heights
        ]
        self.update()

    def sizeHint(self):
        return QSize(_SIZE, _SIZE)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = _SIZE / 2, _SIZE / 2
        radius = 42

        if self._state == "idle":
            bg_color = QColor(Colors.INK)
        elif self._state == "listening":
            bg_color = QColor(Colors.ACCENT)
        elif self._state == "processing":
            bg_color = QColor(Colors.WARN)
        else:
            bg_color = QColor(Colors.INK)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg_color)
        p.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))

        if self._state == "idle":
            px = icon_pixmap("mic", 32, "#ffffff")
            p.drawPixmap(int(cx - 16), int(cy - 16), px)

        elif self._state == "listening":
            bar_w = 4
            gap = 5
            total_w = len(self._bar_heights) * bar_w + (len(self._bar_heights) - 1) * gap
            start_x = cx - total_w / 2
            max_h = 28

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#ffffff"))
            for i, h in enumerate(self._bar_heights):
                bh = max(6, h * max_h)
                bx = start_x + i * (bar_w + gap)
                by = cy - bh / 2
                p.drawRoundedRect(QRectF(bx, by, bar_w, bh), 2, 2)

        elif self._state == "processing":
            px = icon_pixmap("sparkle", 32, "#ffffff")
            p.drawPixmap(int(cx - 16), int(cy - 16), px)

        p.end()
