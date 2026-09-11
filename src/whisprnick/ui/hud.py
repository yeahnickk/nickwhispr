from __future__ import annotations

import random

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QApplication,
    QGraphicsOpacityEffect,
)
from PySide6.QtCore import (
    Qt,
    Signal,
    QTimer,
    QPoint,
    QRectF,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics

from whisprnick.ui.styles.theme import Colors, Fonts
from whisprnick.ui.widgets.icons import icon_pixmap


class FloatingHud(QWidget):
    extend_requested = Signal()
    cancel_requested = Signal()
    dismissed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._state = "idle"
        self._elapsed = 0.0
        self._max_duration = 60.0
        self._transcript = ""
        self._seconds_left = 10
        self._app_name = ""
        self._word_count = 0
        self._notice_text = ""
        self._notice_kind = "error"
        self._notice_ms = 3200

        self._bar_heights = [0.3] * 10
        self._bar_timer = QTimer(self)
        self._bar_timer.setInterval(60)
        self._bar_timer.timeout.connect(self._animate_bars)

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._auto_dismiss)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(200)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self._dragging = False
        self._drag_offset = QPoint()

        self._extend_rect = QRectF()
        self._close_rect = QRectF()

        self.setFixedHeight(44)
        self.setFixedWidth(18)
        self.hide()

    # ── State management ──

    @property
    def state(self) -> str:
        return self._state

    def show_notice(self, text: str, kind: str = "error", duration_ms: int = 3200):
        """Small self-dismissing pill for errors and one-line status notes.
        Replaces tray balloons: same spot as the recording pill, sized to
        the text, gone after a few seconds."""
        self._notice_text = (text or "").strip()
        self._notice_kind = kind
        self._notice_ms = max(1200, int(duration_ms))
        body = QFont(Fonts.BODY, 12)
        fm = QFontMetrics(body)
        text_w = fm.horizontalAdvance(self._notice_text)
        self._notice_width = int(max(120, min(360, text_w + 14 + 14 + 14)))
        self.set_state("notice")

    def set_state(self, state: str):
        prev = self._state
        self._state = state
        self._dismiss_timer.stop()
        self._bar_timer.stop()

        if state == "idle":
            self.setFixedWidth(18)
            self.setFixedHeight(18)
            self._fade_out_and_hide()
            return

        if state == "listening":
            self.setFixedWidth(360)
            self.setFixedHeight(44)
            self._bar_timer.start()

        elif state == "warning":
            self.setFixedWidth(280)
            self.setFixedHeight(44)

        elif state == "processing":
            self.setFixedWidth(320)
            self.setFixedHeight(44)

        elif state == "done":
            self.setFixedWidth(320)
            self.setFixedHeight(44)
            self._dismiss_timer.start(2000)

        elif state == "notice":
            self.setFixedWidth(getattr(self, "_notice_width", 240))
            self.setFixedHeight(36)
            self._dismiss_timer.start(self._notice_ms)

        if prev == "idle" or not self.isVisible():
            self._opacity_effect.setOpacity(0.0)
            self.show()
            self._fade_in()
        else:
            self.show()

        self.show_at_taskbar()
        self.update()

    def update_listening(self, elapsed: float, max_duration: float, transcript: str):
        self._elapsed = elapsed
        self._max_duration = max_duration
        self._transcript = transcript
        self.update()

    def update_warning(self, seconds_left: int):
        self._seconds_left = seconds_left
        self.update()

    def update_done(self, app_name: str, word_count: int):
        self._app_name = app_name
        self._word_count = word_count
        self.update()

    def show_at_taskbar(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        full = screen.geometry()
        taskbar_top = geo.bottom()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = taskbar_top - self.height() - 12
        self.move(x, y)

    # ── Drag support ──

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            click_pos = event.position().toPoint()
            if self._state == "warning" and self._extend_rect.contains(click_pos.x(), click_pos.y()):
                self.extend_requested.emit()
                return
            if self._state == "listening" and self._close_rect.contains(click_pos.x(), click_pos.y()):
                self.cancel_requested.emit()
                return
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        super().mouseReleaseEvent(event)

    # ── Paint ──

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._state == "idle":
            self._paint_idle(p)
        elif self._state == "listening":
            self._paint_listening(p)
        elif self._state == "warning":
            self._paint_warning(p)
        elif self._state == "processing":
            self._paint_processing(p)
        elif self._state == "done":
            self._paint_done(p)
        elif self._state == "notice":
            self._paint_notice(p)

        p.end()

    def _paint_idle(self, p: QPainter):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 100))
        p.drawEllipse(QRectF(0, 0, 18, 18))

    def _paint_listening(self, p: QPainter):
        w, h = self.width(), self.height()
        radius = 22.0

        self._draw_shadow(p, w, h, radius, QColor(0, 0, 0, 100))

        bg = QColor(255, 255, 255, 20)
        border = QColor(255, 255, 255, 30)
        pill = QRectF(0, 0, w, h)

        p.setPen(QPen(border, 1))
        p.setBrush(QColor("#1a1612"))
        p.drawRoundedRect(pill, radius, radius)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(pill, radius, radius)

        x_cursor = 8.0

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(Colors.ACCENT))
        circle_y = (h - 32) / 2
        p.drawEllipse(QRectF(x_cursor, circle_y, 32, 32))

        mic_px = icon_pixmap("mic", 18, "#ffffff")
        p.drawPixmap(int(x_cursor + 7), int(circle_y + 7), mic_px)
        x_cursor += 40

        bar_w = 2.5
        bar_gap = 3.5
        bar_max_h = 18.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(Colors.ACCENT))
        for i, bh_frac in enumerate(self._bar_heights):
            bh = max(4, bh_frac * bar_max_h)
            bx = x_cursor + i * (bar_w + bar_gap)
            by = (h - bh) / 2
            p.drawRoundedRect(QRectF(bx, by, bar_w, bh), 1.25, 1.25)
        x_cursor += 10 * (bar_w + bar_gap) + 6

        mono = QFont(Fonts.MONO, 11)
        p.setFont(mono)
        p.setPen(QColor("#ffffff"))
        elapsed_min = int(self._elapsed) // 60
        elapsed_sec = int(self._elapsed) % 60
        max_min = int(self._max_duration) // 60
        max_sec = int(self._max_duration) % 60
        timer_text = f"{elapsed_min}:{elapsed_sec:02d} / {max_min}:{max_sec:02d}"
        fm = QFontMetrics(mono)
        timer_w = fm.horizontalAdvance(timer_text)
        p.drawText(int(x_cursor), int((h + fm.ascent() - fm.descent()) / 2), timer_text)
        x_cursor += timer_w + 10

        body = QFont(Fonts.BODY, 12)
        p.setFont(body)
        p.setPen(QColor(255, 255, 255, 140))
        close_area = 30
        avail_w = w - x_cursor - close_area - 8
        if avail_w > 20 and self._transcript:
            fm_body = QFontMetrics(body)
            elided = fm_body.elidedText(self._transcript, Qt.TextElideMode.ElideRight, int(avail_w))
            p.drawText(int(x_cursor), int((h + fm_body.ascent() - fm_body.descent()) / 2), elided)

        close_size = 14
        close_x = w - close_size - 12
        close_y = (h - close_size) / 2
        self._close_rect = QRectF(close_x - 4, close_y - 4, close_size + 8, close_size + 8)
        # QtSvg doesn't understand #AARRGGBB, so fade via painter opacity.
        x_px = icon_pixmap("x", close_size, "#ffffff")
        p.setOpacity(0.55)
        p.drawPixmap(int(close_x), int(close_y), x_px)
        p.setOpacity(1.0)

    def _paint_warning(self, p: QPainter):
        w, h = self.width(), self.height()
        radius = 22.0

        self._draw_shadow(p, w, h, radius, QColor(0, 0, 0, 80))

        pill = QRectF(0, 0, w, h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#3a2618"))
        p.drawRoundedRect(pill, radius, radius)

        text_color = QColor("#f3d1a8")
        x_cursor = 12.0

        clock_px = icon_pixmap("clock", 16, "#f3d1a8")
        icon_y = (h - 16) / 2
        p.drawPixmap(int(x_cursor), int(icon_y), clock_px)
        x_cursor += 22

        body = QFont(Fonts.BODY, 12)
        body.setWeight(QFont.Weight.Medium)
        p.setFont(body)
        p.setPen(text_color)
        cutoff_text = f"Auto-cutoff in 0:{self._seconds_left:02d}"
        fm = QFontMetrics(body)
        p.drawText(int(x_cursor), int((h + fm.ascent() - fm.descent()) / 2), cutoff_text)
        x_cursor += fm.horizontalAdvance(cutoff_text) + 10

        bar_x = x_cursor
        bar_w = 50.0
        bar_h = 4.0
        bar_y = (h - bar_h) / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 25))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

        fill_frac = max(0.0, min(1.0, 1.0 - self._seconds_left / 60.0))
        if fill_frac > 0:
            p.setBrush(QColor("#f3a85a"))
            p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w * fill_frac, bar_h), 2, 2)
        x_cursor += bar_w + 10

        btn_font = QFont(Fonts.MONO, 10)
        btn_font.setWeight(QFont.Weight.Bold)
        p.setFont(btn_font)
        fm_btn = QFontMetrics(btn_font)
        btn_text = "+30s"
        btn_tw = fm_btn.horizontalAdvance(btn_text)
        btn_w = btn_tw + 14
        btn_h = 24.0
        btn_x = w - btn_w - 10
        btn_y = (h - btn_h) / 2

        self._extend_rect = QRectF(btn_x, btn_y, btn_w, btn_h)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(243, 168, 90, 40))
        p.drawRoundedRect(self._extend_rect, 6, 6)

        p.setPen(QColor("#f3a85a"))
        p.drawText(
            int(btn_x + (btn_w - btn_tw) / 2),
            int(btn_y + (btn_h + fm_btn.ascent() - fm_btn.descent()) / 2),
            btn_text,
        )

    def _paint_processing(self, p: QPainter):
        w, h = self.width(), self.height()
        radius = 22.0

        self._draw_shadow(p, w, h, radius, QColor(0, 0, 0, 100))

        bg = QColor(255, 255, 255, 20)
        border = QColor(255, 255, 255, 30)
        pill = QRectF(0, 0, w, h)

        p.setPen(QPen(border, 1))
        p.setBrush(QColor("#1a1612"))
        p.drawRoundedRect(pill, radius, radius)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(pill, radius, radius)

        x_cursor = 10.0

        circle_size = 28.0
        circle_y = (h - circle_size) / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(Colors.WARN))
        p.drawEllipse(QRectF(x_cursor, circle_y, circle_size, circle_size))

        sparkle_px = icon_pixmap("sparkle", 16, "#ffffff")
        p.drawPixmap(int(x_cursor + 6), int(circle_y + 6), sparkle_px)
        x_cursor += circle_size + 10

        body = QFont(Fonts.BODY, 12)
        p.setFont(body)
        p.setPen(QColor("#ffffff"))
        label = "Cleaning with Qwen…"
        fm = QFontMetrics(body)
        p.drawText(int(x_cursor), int((h + fm.ascent() - fm.descent()) / 2), label)

        mono = QFont(Fonts.MONO, 11)
        p.setFont(mono)
        p.setPen(QColor(255, 255, 255, 120))
        latency = "~480ms"
        fm_mono = QFontMetrics(mono)
        lat_w = fm_mono.horizontalAdvance(latency)
        p.drawText(int(w - lat_w - 14), int((h + fm_mono.ascent() - fm_mono.descent()) / 2), latency)

    def _paint_done(self, p: QPainter):
        w, h = self.width(), self.height()
        radius = 22.0

        self._draw_shadow(p, w, h, radius, QColor(0, 0, 0, 80))

        pill = QRectF(0, 0, w, h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1b3a1f"))
        p.drawRoundedRect(pill, radius, radius)

        x_cursor = 12.0

        check_px = icon_pixmap("check", 16, "#6abf6a")
        icon_y = (h - 16) / 2
        p.drawPixmap(int(x_cursor), int(icon_y), check_px)
        x_cursor += 22

        body = QFont(Fonts.BODY, 12)
        p.setFont(body)
        p.setPen(QColor("#b8e6b8"))
        app = self._app_name or "app"
        done_text = f"Pasted into {app} · {self._word_count} words"
        fm = QFontMetrics(body)
        avail = w - x_cursor - 14
        elided = fm.elidedText(done_text, Qt.TextElideMode.ElideRight, int(avail))
        p.drawText(int(x_cursor), int((h + fm.ascent() - fm.descent()) / 2), elided)

    def _paint_notice(self, p: QPainter):
        w, h = self.width(), self.height()
        radius = h / 2

        self._draw_shadow(p, w, h, radius, QColor(0, 0, 0, 80))

        pill = QRectF(0, 0, w, h)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(QColor("#1a1612"))
        p.drawRoundedRect(pill, radius, radius)

        dot = QColor("#e06c5b") if self._notice_kind == "error" else QColor("#8fb8e6")
        x_cursor = 14.0
        dot_size = 8.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(dot)
        p.drawEllipse(QRectF(x_cursor, (h - dot_size) / 2, dot_size, dot_size))
        x_cursor += dot_size + 10

        body = QFont(Fonts.BODY, 12)
        p.setFont(body)
        p.setPen(QColor(255, 255, 255, 230))
        fm = QFontMetrics(body)
        avail = w - x_cursor - 14
        elided = fm.elidedText(self._notice_text, Qt.TextElideMode.ElideRight, int(avail))
        p.drawText(int(x_cursor), int((h + fm.ascent() - fm.descent()) / 2), elided)

    def _draw_shadow(self, p: QPainter, w: float, h: float, radius: float, color: QColor):
        shadow_offset = 8
        shadow_spread = 20
        shadow_color = QColor(color)
        shadow_color.setAlpha(60)
        for i in range(shadow_spread, 0, -4):
            alpha = max(1, shadow_color.alpha() * i // shadow_spread)
            c = QColor(shadow_color)
            c.setAlpha(alpha)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            inflate = i * 0.5
            p.drawRoundedRect(
                QRectF(-inflate, shadow_offset - inflate, w + inflate * 2, h + inflate * 2),
                radius + inflate,
                radius + inflate,
            )

    # ── Animation helpers ──

    def _animate_bars(self):
        self._bar_heights = [
            max(0.1, min(1.0, h + random.uniform(-0.25, 0.25)))
            for h in self._bar_heights
        ]
        self.update()

    def _fade_in(self):
        self._fade_anim.stop()
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def _fade_out_and_hide(self):
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(self._on_fade_out_done)
        self._fade_anim.start()

    def _on_fade_out_done(self):
        try:
            self._fade_anim.finished.disconnect(self._on_fade_out_done)
        except RuntimeError:
            pass
        if self._state == "idle":
            self.hide()

    def _auto_dismiss(self):
        self._bar_timer.stop()
        self._state = "idle"
        self.dismissed.emit()
        self._fade_out_and_hide()
