from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen, Qt
from PySide6.QtWidgets import QSystemTrayIcon, QMenu

from whisprnick.config import APP_NAME, APP_SUBTITLE, DEFAULT_HOTKEY
from whisprnick.ui.styles.theme import Colors


def _make_icon(tint: QColor | None = None) -> QIcon:
    size = 32
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    bg = QColor(Colors.INK) if tint is None else tint
    p.setBrush(QBrush(bg))
    p.setPen(Qt.NoPen)
    p.drawEllipse(0, 0, size, size)

    pen = QPen(QColor("#ffffff"))
    pen.setWidth(2)
    p.setPen(pen)
    p.setBrush(QBrush(QColor("#ffffff")))

    cx = size // 2
    p.drawRoundedRect(cx - 3, 7, 6, 10, 3, 3)

    p.setBrush(Qt.NoBrush)
    p.drawArc(cx - 6, 12, 12, 10, 0, 180 * 16)

    p.drawLine(cx, 22, cx, 26)
    p.drawLine(cx - 3, 26, cx + 3, 26)

    p.end()
    return QIcon(pm)


_ICONS: dict[str, QIcon] = {}


def _get_icon(state: str) -> QIcon:
    if state not in _ICONS:
        tints = {
            "idle": None,
            "recording": QColor(Colors.BAD),
            "processing": QColor(Colors.WARN),
        }
        _ICONS[state] = _make_icon(tints.get(state))
    return _ICONS[state]


class SystemTray(QSystemTrayIcon):
    toggle_window = Signal()
    start_dictation = Signal()
    quit_app = Signal()

    def __init__(self, icon: QIcon = None, parent=None, hotkey: str = DEFAULT_HOTKEY):
        super().__init__(icon or _get_icon("idle"), parent)
        self._custom_icon = icon
        self._hotkey = hotkey
        self.setToolTip(f"{APP_NAME} — {APP_SUBTITLE}")
        self._build_menu()

    def set_hotkey(self, combo: str):
        self._hotkey = combo
        self._build_menu()
        self.activated.connect(self._on_activated)

    def _build_menu(self):
        menu = QMenu()

        act_dictate = menu.addAction(f"Start Dictation\t{self._hotkey}")
        act_dictate.triggered.connect(self.start_dictation.emit)

        menu.addSeparator()

        act_open = menu.addAction(f"Open {APP_NAME}")
        act_open.triggered.connect(self.toggle_window.emit)

        menu.addSeparator()

        act_quit = menu.addAction("Quit")
        act_quit.triggered.connect(self.quit_app.emit)

        self.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_window.emit()

    def set_state(self, state: str):
        self.setIcon(_get_icon(state))
