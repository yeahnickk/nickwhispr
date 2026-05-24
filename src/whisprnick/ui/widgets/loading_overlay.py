from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QColor, QFont, QLinearGradient

from whisprnick.ui.styles.theme import Colors, Fonts


class _ProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self._progress = 0.0
        self._pulse_offset = 0.0
        self._indeterminate = True

        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_progress(self, value: float):
        self._progress = max(0.0, min(1.0, value))
        if value >= 1.0:
            self._indeterminate = False
        self.update()

    def _tick(self):
        self._pulse_offset += 0.012
        if self._pulse_offset > 2.0:
            self._pulse_offset = -0.4
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)

        w, h = self.width(), self.height()

        p.setBrush(QColor(Colors.RULE))
        p.drawRoundedRect(0, 0, w, h, 2, 2)

        if self._indeterminate:
            pulse_w = int(w * 0.35)
            pulse_x = int((self._pulse_offset) * w) - pulse_w // 2
            grad = QLinearGradient(pulse_x, 0, pulse_x + pulse_w, 0)
            grad.setColorAt(0.0, QColor(Colors.RULE))
            grad.setColorAt(0.4, QColor(Colors.ACCENT))
            grad.setColorAt(0.6, QColor(Colors.ACCENT))
            grad.setColorAt(1.0, QColor(Colors.RULE))
            p.setBrush(grad)
            p.drawRoundedRect(max(0, pulse_x), 0, pulse_w, h, 2, 2)
        else:
            fill_w = max(4, int(w * self._progress))
            p.setBrush(QColor(Colors.ACCENT))
            p.drawRoundedRect(0, 0, fill_w, h, 2, 2)

        p.end()

    def stop(self):
        self._timer.stop()


class LoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: transparent;")

        self._opacity = 1.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addStretch(3)

        center = QVBoxLayout()
        center.setSpacing(16)
        center.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._brand = QLabel("N", self)
        self._brand.setFixedSize(56, 56)
        self._brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._brand.setStyleSheet(
            f"background: {Colors.INK}; color: {Colors.PAPER}; border-radius: 14px; "
            f"font-family: \"{Fonts.BODY}\"; font-size: 24px; font-weight: 700;"
        )
        center.addWidget(self._brand, 0, Qt.AlignmentFlag.AlignCenter)

        self._title = QLabel("NickWhispr", self)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(
            f"font-family: \"{Fonts.SERIF}\"; font-size: 28px; color: {Colors.INK}; "
            f"letter-spacing: -0.5px; background: transparent;"
        )
        center.addWidget(self._title)

        self._status = QLabel("Loading Whisper model...", self)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(
            f"font-size: 13px; color: {Colors.MUTE}; background: transparent;"
        )
        center.addWidget(self._status)

        bar_container = QWidget(self)
        bar_container.setFixedWidth(260)
        bar_container.setStyleSheet("background: transparent;")
        bar_layout = QVBoxLayout(bar_container)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        self._bar = _ProgressBar(self)
        bar_layout.addWidget(self._bar)
        center.addWidget(bar_container, 0, Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(center)
        layout.addStretch(4)

    def set_status(self, text: str):
        self._status.setText(text)

    def set_progress(self, value: float):
        self._bar.set_progress(value)

    def fade_out(self, on_done=None):
        self._bar.stop()
        self._bar.set_progress(1.0)
        self._status.setText("Ready")

        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(400)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self._opacity_timer = QTimer(self)
        self._opacity_timer.setInterval(16)
        self._fade_step = 1.0

        def tick():
            self._fade_step -= 0.04
            if self._fade_step <= 0:
                self._opacity_timer.stop()
                self.hide()
                if on_done:
                    on_done()
                return
            self.setStyleSheet(f"background: transparent;")
            self._opacity = max(0.0, self._fade_step)
            self.update()

        self._opacity_timer.timeout.connect(tick)
        self._opacity_timer.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setOpacity(self._opacity)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(Colors.PAPER))
        p.drawRect(self.rect())
        p.end()

        self._brand.setVisible(self._opacity > 0.05)
        self._title.setVisible(self._opacity > 0.05)
        self._status.setVisible(self._opacity > 0.05)
        self._bar.setVisible(self._opacity > 0.05)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setGeometry(self.parent().rect() if self.parent() else self.rect())
