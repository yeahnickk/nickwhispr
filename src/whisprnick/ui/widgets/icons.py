"""SVG icon system for the Whispr Vozi PySide6 desktop app.

Provides 29 named icons rendered on-demand as QPixmap / QIcon / QLabel
at any size and stroke color.  Results are cached by (name, size, color).
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel

# ---------------------------------------------------------------------------
# SVG path fragments – every icon uses the same viewBox / stroke style.
# Only the *inner* elements differ.
# ---------------------------------------------------------------------------

_ICON_SVG: dict[str, str] = {
    "mic": (
        '<rect x="9" y="3" width="6" height="12" rx="3"/>'
        '<path d="M5 11a7 7 0 0 0 14 0"/>'
        '<path d="M12 18v3"/>'
    ),
    "history": (
        '<path d="M3 12a9 9 0 1 0 3-6.7"/>'
        '<path d="M3 4v5h5"/>'
        '<path d="M12 7v5l3 2"/>'
    ),
    "chart": (
        '<path d="M3 3v18h18"/>'
        '<path d="M7 14l4-4 3 3 5-6"/>'
    ),
    "book": (
        '<path d="M4 4h11a4 4 0 0 1 4 4v13H8a4 4 0 0 1-4-4z"/>'
        '<path d="M4 4v13"/>'
    ),
    "wand": (
        '<path d="M15 4l2 2"/>'
        '<path d="M4 20l11-11"/>'
        '<path d="M14 5l5 5"/>'
        '<path d="M20 4l.5.5"/>'
        '<path d="M19 13l1 1"/>'
        '<path d="M5 8l1 1"/>'
    ),
    "shield": (
        '<path d="M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6z"/>'
    ),
    "settings": (
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1'
        'a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1'
        'a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8'
        'l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1'
        'a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8'
        'l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1'
        'a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8'
        'l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4'
        'h-.1a1.7 1.7 0 0 0-1.5 1z"/>'
    ),
    "play": (
        '<path d="M6 4l14 8L6 20z"/>'
    ),
    "pause": (
        '<rect x="6" y="5" width="4" height="14"/>'
        '<rect x="14" y="5" width="4" height="14"/>'
    ),
    "stop": (
        '<rect x="6" y="6" width="12" height="12" rx="1"/>'
    ),
    "plus": (
        '<path d="M12 5v14M5 12h14"/>'
    ),
    "search": (
        '<circle cx="11" cy="11" r="7"/>'
        '<path d="M21 21l-4.3-4.3"/>'
    ),
    "chev": (
        '<path d="M9 6l6 6-6 6"/>'
    ),
    "chevDown": (
        '<path d="M6 9l6 6 6-6"/>'
    ),
    "copy": (
        '<rect x="9" y="9" width="11" height="11" rx="2"/>'
        '<rect x="4" y="4" width="11" height="11" rx="2"/>'
    ),
    "trash": (
        '<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2'
        'M6 6l1 14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-14"/>'
    ),
    "edit": (
        '<path d="M11 4H4v16h16v-7"/>'
        '<path d="M18.5 2.5a2.1 2.1 0 0 1 3 3L12 15l-4 1 1-4z"/>'
    ),
    "check": (
        '<path d="M5 12l5 5L20 7"/>'
    ),
    "x": (
        '<path d="M6 6l12 12M18 6L6 18"/>'
    ),
    "sparkle": (
        '<path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z"/>'
        '<path d="M19 3l.7 1.8L21 5.5l-1.3.7L19 8l-.7-1.8L17 5.5l1.3-.7z"/>'
    ),
    "bolt": (
        '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>'
    ),
    "clock": (
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="M12 7v5l3 2"/>'
    ),
    "keyboard": (
        '<rect x="2" y="6" width="20" height="12" rx="2"/>'
        '<path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/>'
    ),
    "audio": (
        '<path d="M3 10v4M7 7v10M11 4v16M15 8v8M19 11v2"/>'
    ),
    "dollar": (
        '<path d="M12 2v20M17 6H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>'
    ),
    "cpu": (
        '<rect x="5" y="5" width="14" height="14" rx="2"/>'
        '<rect x="9" y="9" width="6" height="6"/>'
        '<path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2"/>'
    ),
    "cloud": (
        '<path d="M17 18a4 4 0 0 0 0-8 6 6 0 0 0-11.5 1.5A4 4 0 0 0 6 18z"/>'
    ),
    "arrow": (
        '<path d="M5 12h14M13 6l6 6-6 6"/>'
    ),
    "star": (
        '<path d="M12 2l3 7 7 .8-5.3 4.7L18 22l-6-3.5L6 22l1.3-7.5L2 9.8 9 9z"/>'
    ),
}

# All available icon names (tuple for fast membership checks).
ICON_NAMES: tuple[str, ...] = tuple(_ICON_SVG)


def _build_svg(name: str, color: str) -> bytes:
    """Return a complete SVG document for *name* with the given stroke *color*."""
    inner = _ICON_SVG[name]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round">'
        f"{inner}</svg>"
    )
    return svg.encode("utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Cache keyed by (name, size, color).  256 entries covers typical usage.
@lru_cache(maxsize=256)
def icon_pixmap(name: str, size: int = 16, color: str = "#1d1815") -> QPixmap:
    """Render the named icon as a ``QPixmap`` at *size* x *size* pixels.

    Parameters
    ----------
    name:
        One of the keys in :data:`ICON_NAMES`.
    size:
        Width and height in pixels (default 16).
    color:
        CSS color string used as the stroke color (default ``#1d1815``).

    Raises
    ------
    KeyError
        If *name* is not a recognised icon.
    """
    svg_bytes = _build_svg(name, color)
    renderer = QSvgRenderer(QByteArray(svg_bytes))

    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    renderer.render(painter)
    painter.end()

    return QPixmap.fromImage(image)


def icon(name: str, size: int = 16, color: str = "#1d1815") -> QIcon:
    """Return the named icon as a ``QIcon``.

    See :func:`icon_pixmap` for parameter details.
    """
    return QIcon(icon_pixmap(name, size, color))


def icon_label(name: str, size: int = 16, color: str = "#1d1815") -> QLabel:
    """Create a ``QLabel`` displaying the named icon.

    The label has a fixed size matching *size* and transparent background.

    See :func:`icon_pixmap` for parameter details.
    """
    lbl = QLabel()
    lbl.setPixmap(icon_pixmap(name, size, color))
    lbl.setFixedSize(size, size)
    lbl.setStyleSheet("background: transparent;")
    return lbl
