from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPoint, QSize
from PySide6.QtGui import QColor, QFont, QPainter, QCursor, QMouseEvent, QCloseEvent
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QFrame,
    QSizePolicy,
    QGraphicsDropShadowEffect,
)

from whisprnick.ui.styles.theme import Colors, Fonts, get_stylesheet
from whisprnick.ui.widgets.icons import icon_pixmap
from whisprnick.config import (
    APP_NAME,
    APP_SUBTITLE,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    SIDEBAR_WIDTH,
    TITLEBAR_HEIGHT,
)
from whisprnick.ui.pages.home import HomePage
from whisprnick.ui.pages.history import HistoryPage
from whisprnick.ui.pages.insights import InsightsPage
from whisprnick.ui.pages.dictionary import DictionaryPage
from whisprnick.ui.pages.cleanup import CleanupPage
from whisprnick.ui.pages.hud_config import HudConfigPage
from whisprnick.ui.pages.safeguards import SafeguardsPage
from whisprnick.ui.pages.settings import SettingsPage
from whisprnick.ui.widgets.loading_overlay import LoadingOverlay


NAV_ITEMS = [
    ("Home", "mic"),
    ("History", "history"),
    ("Insights", "chart"),
    ("Dictionary", "book"),
    ("Cleanup", "wand"),
    ("HUD widget", "bolt"),
    ("Safeguards", "shield"),
    ("Settings", "settings"),
]


class _TitleBarButton(QPushButton):
    def __init__(self, symbol: str, is_close: bool = False, parent=None):
        super().__init__(symbol, parent)
        self._is_close = is_close
        self.setFixedSize(46, TITLEBAR_HEIGHT)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFont(QFont(Fonts.BODY, 10))
        self._apply_style(False)

    def _apply_style(self, hovered: bool):
        if self._is_close:
            if hovered:
                bg = "#c0413a"
                fg = "#ffffff"
            else:
                bg = "transparent"
                fg = Colors.INK_2
        else:
            if hovered:
                bg = "rgba(40,30,15,0.06)"
                fg = Colors.INK
            else:
                bg = "transparent"
                fg = Colors.INK_2
        self.setStyleSheet(
            f"QPushButton {{ background: {bg}; color: {fg}; border: none; "
            f"font-size: 11px; }}"
        )

    def enterEvent(self, event):
        self._apply_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_style(False)
        super().leaveEvent(event)


class _TitleBar(QWidget):
    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(TITLEBAR_HEIGHT)
        self.setStyleSheet(
            f"background: rgba(247,241,228,0.8); "
            f"border-bottom: 1px solid {Colors.RULE};"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        brand_mark = QLabel("N")
        brand_mark.setFixedSize(14, 14)
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_mark.setStyleSheet(
            f"background: {Colors.INK}; color: {Colors.PAPER}; "
            f"border-radius: 3px; font-family: \"{Fonts.BODY}\"; "
            f"font-size: 9px; font-weight: 700;"
        )
        layout.addWidget(brand_mark)
        layout.addSpacing(7)

        app_label = QLabel(APP_NAME)
        app_label.setStyleSheet(
            f"background: transparent; color: {Colors.INK}; "
            f"font-family: \"{Fonts.BODY}\"; font-size: 12px; font-weight: 600;"
        )
        layout.addWidget(app_label)
        layout.addSpacing(5)

        subtitle = QLabel(f"— {APP_SUBTITLE}")
        subtitle.setStyleSheet(
            f"background: transparent; color: {Colors.MUTE}; "
            f"font-family: \"{Fonts.BODY}\"; font-size: 12px;"
        )
        layout.addWidget(subtitle)

        layout.addStretch()

        self._btn_min = _TitleBarButton("–")
        self._btn_max = _TitleBarButton("□")
        self._btn_close = _TitleBarButton("✕", is_close=True)

        self._btn_min.clicked.connect(self.minimize_clicked.emit)
        self._btn_max.clicked.connect(self.maximize_clicked.emit)
        self._btn_close.clicked.connect(self.close_clicked.emit)

        layout.addWidget(self._btn_min)
        layout.addWidget(self._btn_max)
        layout.addWidget(self._btn_close)

        self._drag_pos: QPoint | None = None

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_clicked.emit()


class _NavButton(QPushButton):
    def __init__(self, label: str, icon_name: str, parent=None):
        super().__init__(parent)
        self._label_text = label
        self._icon_name = icon_name
        self._active = False
        self._show_dot = False
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(34)
        self._refresh()

    def set_active(self, active: bool):
        self._active = active
        self._refresh()

    def set_dot_visible(self, visible: bool):
        self._show_dot = visible
        self.update()

    def _refresh(self):
        if self._active:
            icon_color = Colors.INK
            text_color = Colors.INK
            bg = Colors.PAPER_3
            border = f"1px solid {Colors.RULE}"
            weight = "500"
        else:
            icon_color = Colors.MUTE
            text_color = Colors.MUTE
            bg = "transparent"
            border = "1px solid transparent"
            weight = "400"

        px = icon_pixmap(self._icon_name, 15, icon_color)
        self.setIcon(px)
        self.setIconSize(QSize(15, 15))
        self.setText(self._label_text)
        self.setStyleSheet(
            f"QPushButton {{ background: {bg}; color: {text_color}; "
            f"border: {border}; border-radius: 8px; "
            f"padding: 8px 10px; font-family: \"{Fonts.BODY}\"; "
            f"font-size: 13px; font-weight: {weight}; text-align: left; }}"
            f"QPushButton:hover {{ background: {Colors.PAPER_3 if self._active else 'rgba(40,30,15,0.04)'}; }}"
        )

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._show_dot:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(Colors.ACCENT))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(self.width() - 16, (self.height() - 6) // 2, 6, 6)
            painter.end()


class _Sidebar(QWidget):
    nav_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setStyleSheet(
            f"_Sidebar {{ background: {Colors.PAPER_2}; "
            f"border-right: 1px solid {Colors.RULE}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 12, 10, 10)
        root.setSpacing(0)

        self._nav_buttons: dict[str, _NavButton] = {}
        for label, ico in NAV_ITEMS:
            btn = _NavButton(label, ico)
            btn.clicked.connect(lambda checked=False, n=label: self._on_nav(n))
            self._nav_buttons[label] = btn
            root.addWidget(btn)
            root.addSpacing(2)

        root.addStretch()

        self._footer = QFrame()
        self._footer.setStyleSheet(
            f"QFrame {{ background: {Colors.PAPER_3}; border: 1px solid {Colors.RULE}; "
            f"border-radius: 10px; padding: 10px; }}"
        )
        footer_lay = QVBoxLayout(self._footer)
        footer_lay.setContentsMargins(0, 0, 0, 0)
        footer_lay.setSpacing(6)

        from whisprnick.config import OLLAMA_MODEL, WHISPER_MODEL as _WM

        whisper_row = QHBoxLayout()
        whisper_row.setContentsMargins(0, 0, 0, 0)
        whisper_row.setSpacing(5)

        self._whisper_dot = QLabel()
        self._whisper_dot.setFixedSize(6, 6)
        self._whisper_dot.setStyleSheet(
            f"background: {Colors.GOOD}; border-radius: 3px; border: none;"
        )
        whisper_row.addWidget(self._whisper_dot, 0, Qt.AlignmentFlag.AlignVCenter)

        self._whisper_label = QLabel(f"whisper · {_WM}")
        self._whisper_label.setStyleSheet(
            f"background: transparent; color: {Colors.MUTE}; "
            f"font-family: \"{Fonts.BODY}\"; font-size: 11px; border: none;"
        )
        whisper_row.addWidget(self._whisper_label)
        whisper_row.addStretch()
        footer_lay.addLayout(whisper_row)

        ollama_row = QHBoxLayout()
        ollama_row.setContentsMargins(0, 0, 0, 0)
        ollama_row.setSpacing(5)

        self._ollama_dot = QLabel()
        self._ollama_dot.setFixedSize(6, 6)
        self._ollama_dot.setStyleSheet(
            f"background: {Colors.GOOD}; border-radius: 3px; border: none;"
        )
        ollama_row.addWidget(self._ollama_dot, 0, Qt.AlignmentFlag.AlignVCenter)

        self._ollama_label = QLabel(f"{OLLAMA_MODEL} · ready")
        self._ollama_label.setStyleSheet(
            f"background: transparent; color: {Colors.MUTE}; "
            f"font-family: \"{Fonts.BODY}\"; font-size: 11px; border: none;"
        )
        ollama_row.addWidget(self._ollama_label)
        ollama_row.addStretch()
        footer_lay.addLayout(ollama_row)

        root.addWidget(self._footer)

        self.set_active("Home")

    def _on_nav(self, name: str):
        self.set_active(name)
        self.nav_clicked.emit(name)

    def set_active(self, name: str):
        for key, btn in self._nav_buttons.items():
            btn.set_active(key == name)

    def set_recording_dot(self, visible: bool):
        home_btn = self._nav_buttons.get("Home")
        if home_btn:
            home_btn.set_dot_visible(visible)

    def update_ollama_status(self, model: str, ready: bool):
        dot_color = Colors.GOOD if ready else Colors.MUTE_2
        self._ollama_dot.setStyleSheet(
            f"background: {dot_color}; border-radius: 3px; border: none;"
        )
        status = "ready" if ready else "offline"
        self._ollama_label.setText(f"{model} · {status}")

class MainWindow(QMainWindow):
    page_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"{APP_NAME} — {APP_SUBTITLE}")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(800, 500)
        self.setStyleSheet(get_stylesheet())

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # No custom titlebar — using native window frame for resize/snap support

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._sidebar = _Sidebar()
        self._sidebar.nav_clicked.connect(self._on_nav)
        body.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {Colors.PAPER};")
        body.addWidget(self._stack, 1)

        outer.addLayout(body, 1)

        self._pages: dict[str, int] = {}
        self._current_page: str = ""
        self._rec_state: str = "idle"

        page_map = {
            "Home": HomePage,
            "History": HistoryPage,
            "Insights": InsightsPage,
            "Dictionary": DictionaryPage,
            "Cleanup": CleanupPage,
            "HUD widget": HudConfigPage,
            "Safeguards": SafeguardsPage,
            "Settings": SettingsPage,
        }
        for label, _ in NAV_ITEMS:
            cls = page_map.get(label)
            if cls:
                self.add_page(label, cls())
            else:
                placeholder = QLabel(label)
                placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                placeholder.setStyleSheet(
                    f"background: transparent; color: {Colors.MUTE}; "
                    f"font-family: \"{Fonts.SERIF}\"; font-size: 22px;"
                )
                self.add_page(label, placeholder)

        self.set_page("Home")

        self._loading_overlay = LoadingOverlay(central)
        self._loading_overlay.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        self._loading_overlay.raise_()
        self._loading_overlay.show()

    def _on_nav(self, name: str):
        self.set_page(name)

    def add_page(self, name: str, widget: QWidget):
        idx = self._stack.addWidget(widget)
        self._pages[name] = idx

    def set_page(self, name: str):
        idx = self._pages.get(name)
        if idx is None:
            return
        self._stack.setCurrentIndex(idx)
        self._sidebar.set_active(name)
        self._current_page = name
        self.page_changed.emit(name)

    def set_recording_state(self, state: str):
        self._rec_state = state
        self._sidebar.set_recording_dot(state == "listening")

    def update_ollama_status(self, model: str, ready: bool):
        self._sidebar.update_ollama_status(model, ready)

    def closeEvent(self, event: QCloseEvent):
        from PySide6.QtWidgets import QApplication
        event.accept()
        QApplication.quit()

    def set_loading_status(self, text: str):
        if hasattr(self, '_loading_overlay') and self._loading_overlay.isVisible():
            self._loading_overlay.set_status(text)

    def dismiss_loading(self):
        if hasattr(self, '_loading_overlay') and self._loading_overlay.isVisible():
            self._loading_overlay.fade_out()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading_overlay'):
            self._loading_overlay.setGeometry(self.centralWidget().rect())

    def start_dictation(self):
        self.set_page("Home")

