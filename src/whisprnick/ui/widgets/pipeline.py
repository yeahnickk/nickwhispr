from __future__ import annotations

from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPainter, QPen, QColor

from whisprnick.ui.styles.theme import Colors, Fonts
from whisprnick.ui.widgets.icons import icon_pixmap


class _DashedLine(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setMinimumWidth(10)
        self.setMaximumWidth(30)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(Colors.MUTE_2))
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setWidthF(1.2)
        p.setPen(pen)
        mid_y = self.height() // 2
        p.drawLine(0, mid_y, self.width(), mid_y)
        p.end()


class _PipelineNode(QWidget):
    def __init__(self, icon_name: str, label: str, bg: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self.setMaximumWidth(52)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_box = QWidget(self)
        icon_box.setFixedSize(26, 26)
        icon_box.setStyleSheet(
            f"background: {bg}; "
            f"border-radius: 7px; "
            f"border: 1px solid {Colors.RULE};"
        )

        icon_lbl = QLabel(icon_box)
        px = icon_pixmap(icon_name, 14, Colors.INK_2)
        icon_lbl.setPixmap(px)
        icon_lbl.setFixedSize(14, 14)
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        icon_lbl.move(6, 6)

        layout.addWidget(icon_box, 0, Qt.AlignmentFlag.AlignCenter)

        text_lbl = QLabel(label, self)
        text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_lbl.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; "
            f"font-size: 9px; "
            f"color: {Colors.MUTE}; "
            f"background: transparent;"
        )
        layout.addWidget(text_lbl)


_NODES = [
    ("mic", "capture", Colors.PAPER_3),
    ("audio", "Whisper", Colors.ACCENT_SOFT),
    ("sparkle", "Qwen", Colors.PAPER_3),
    ("edit", "paste", Colors.PAPER_3),
]


class PipelineWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)

        for i, (icon_name, label, bg) in enumerate(_NODES):
            if i > 0:
                dash = _DashedLine(self)
                layout.addWidget(dash, 1)
            node = _PipelineNode(icon_name, label, bg, self)
            layout.addWidget(node, 0)
