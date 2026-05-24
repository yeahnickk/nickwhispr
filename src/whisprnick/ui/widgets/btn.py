from __future__ import annotations

from PySide6.QtWidgets import QPushButton
from PySide6.QtGui import QIcon, QCursor
from PySide6.QtCore import Qt

from whisprnick.ui.styles.theme import Colors, Fonts
from whisprnick.ui.widgets.icons import icon_pixmap

_VARIANTS = {
    "primary": {
        "bg": Colors.INK,
        "color": Colors.PAPER,
        "border": Colors.INK,
    },
    "accent": {
        "bg": Colors.ACCENT,
        "color": "#ffffff",
        "border": Colors.ACCENT_2,
    },
    "ghost": {
        "bg": "transparent",
        "color": Colors.INK_2,
        "border": "transparent",
    },
    "soft": {
        "bg": "rgba(40,30,15,0.05)",
        "color": Colors.INK,
        "border": "rgba(40,30,15,0.06)",
    },
    "outline": {
        "bg": Colors.PAPER_3,
        "color": Colors.INK,
        "border": Colors.RULE,
    },
    "danger": {
        "bg": "transparent",
        "color": Colors.BAD,
        "border": "transparent",
    },
}

_SIZES = {
    "sm": {"padding": "5px 10px", "font_size": 12, "radius": 8},
    "md": {"padding": "8px 14px", "font_size": 13, "radius": 9},
    "lg": {"padding": "11px 18px", "font_size": 14, "radius": 10},
}


class Btn(QPushButton):
    def __init__(
        self,
        text: str = "",
        variant: str = "ghost",
        size: str = "md",
        icon_name: str | None = None,
        parent=None,
    ):
        super().__init__(text, parent)

        v = _VARIANTS.get(variant, _VARIANTS["ghost"])
        s = _SIZES.get(size, _SIZES["md"])

        self.setStyleSheet(
            f"Btn {{ "
            f"background: {v['bg']}; "
            f"color: {v['color']}; "
            f"border: 1px solid {v['border']}; "
            f"border-radius: {s['radius']}px; "
            f"padding: {s['padding']}; "
            f"font-size: {s['font_size']}px; "
            f"font-weight: 500; "
            f"font-family: \"{Fonts.BODY}\"; "
            f"}} "
            f"Btn:hover {{ opacity: 0.85; }}"
        )
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        if icon_name:
            px = icon_pixmap(icon_name, s["font_size"], v["color"])
            self.setIcon(QIcon(px))
