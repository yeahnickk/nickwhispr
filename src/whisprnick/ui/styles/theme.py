class Colors:
    BG = "#f0e9dc"
    PAPER = "#f7f1e4"
    PAPER_2 = "#fbf6ec"
    PAPER_3 = "#ffffff"
    INK = "#1d1815"
    INK_2 = "#4a423a"
    MUTE = "#8a7e6f"
    MUTE_2 = "#b5a995"
    RULE = "#e6dcc8"
    RULE_2 = "#ede4d2"
    ACCENT = "#2e6dd8"
    ACCENT_2 = "#1e5cc8"
    ACCENT_SOFT = "#e4ecfb"
    GOOD = "#4a7c4a"
    WARN = "#c08a3a"
    BAD = "#b8503a"


class Fonts:
    BODY = "DM Sans"
    SERIF = "Instrument Serif"
    MONO = "JetBrains Mono"


def get_stylesheet() -> str:
    c = Colors
    f = Fonts
    return f"""

    /* ── Base ── */

    QWidget {{
        background: {c.PAPER};
        color: {c.INK};
        font-family: "{f.BODY}";
        font-size: 13px;
    }}

    /* ── Labels ── */

    QLabel {{
        background: transparent;
        padding: 0;
    }}

    QLabel[role="title"] {{
        font-family: "{f.SERIF}";
        font-size: 22px;
        color: {c.INK};
    }}

    QLabel[role="subtitle"] {{
        font-size: 13px;
        color: {c.MUTE};
    }}

    QLabel[role="heading"] {{
        font-size: 15px;
        font-weight: 600;
        color: {c.INK};
    }}

    QLabel[role="muted"] {{
        color: {c.MUTE};
        font-size: 12px;
    }}

    QLabel[role="mono"] {{
        font-family: "{f.MONO}";
        font-size: 12px;
        color: {c.INK_2};
    }}

    QLabel[role="accent"] {{
        color: {c.ACCENT};
        font-weight: 600;
    }}

    QLabel[role="good"] {{
        color: {c.GOOD};
    }}

    QLabel[role="warn"] {{
        color: {c.WARN};
    }}

    QLabel[role="bad"] {{
        color: {c.BAD};
    }}

    /* ── Buttons ── */

    QPushButton {{
        background: {c.PAPER_2};
        color: {c.INK};
        border: 1px solid {c.RULE};
        border-radius: 8px;
        padding: 7px 16px;
        font-size: 13px;
        font-weight: 500;
    }}

    QPushButton:hover {{
        background: {c.PAPER_3};
        border-color: {c.MUTE_2};
    }}

    QPushButton:pressed {{
        background: {c.RULE_2};
    }}

    QPushButton:disabled {{
        color: {c.MUTE_2};
        background: {c.PAPER};
        border-color: {c.RULE_2};
    }}

    QPushButton[role="primary"] {{
        background: {c.ACCENT};
        color: {c.PAPER_3};
        border: none;
        font-weight: 600;
    }}

    QPushButton[role="primary"]:hover {{
        background: {c.ACCENT_2};
    }}

    QPushButton[role="primary"]:pressed {{
        background: {c.ACCENT_2};
    }}

    QPushButton[role="primary"]:disabled {{
        background: {c.MUTE_2};
        color: {c.PAPER};
    }}

    QPushButton[role="flat"] {{
        background: transparent;
        border: none;
        color: {c.INK_2};
        padding: 5px 10px;
    }}

    QPushButton[role="flat"]:hover {{
        background: {c.RULE_2};
        border-radius: 6px;
    }}

    QPushButton[role="danger"] {{
        background: {c.BAD};
        color: {c.PAPER_3};
        border: none;
    }}

    QPushButton[role="danger"]:hover {{
        background: #a34530;
    }}

    /* ── Text Inputs ── */

    QLineEdit {{
        background: {c.PAPER_3};
        color: {c.INK};
        border: 1px solid {c.RULE};
        border-radius: 8px;
        padding: 7px 10px;
        font-size: 13px;
        selection-background-color: {c.ACCENT_SOFT};
    }}

    QLineEdit:focus {{
        border-color: {c.ACCENT};
    }}

    QLineEdit:disabled {{
        background: {c.PAPER};
        color: {c.MUTE_2};
    }}

    QTextEdit {{
        background: {c.PAPER_3};
        color: {c.INK};
        border: 1px solid {c.RULE};
        border-radius: 8px;
        padding: 8px;
        font-size: 13px;
        selection-background-color: {c.ACCENT_SOFT};
    }}

    QTextEdit:focus {{
        border-color: {c.ACCENT};
    }}

    /* ── Scroll Bars ── */

    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 2px 0;
    }}

    QScrollBar::handle:vertical {{
        background: rgba(181, 169, 149, 0.45);
        min-height: 30px;
        border-radius: 3px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: rgba(138, 126, 111, 0.55);
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0;
        background: none;
        border: none;
    }}

    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 6px;
        margin: 0 2px;
    }}

    QScrollBar::handle:horizontal {{
        background: rgba(181, 169, 149, 0.45);
        min-width: 30px;
        border-radius: 3px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background: rgba(138, 126, 111, 0.55);
    }}

    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        width: 0;
        background: none;
        border: none;
    }}

    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}

    /* ── Slider ── */

    QSlider::groove:horizontal {{
        background: {c.RULE};
        height: 4px;
        border-radius: 2px;
    }}

    QSlider::handle:horizontal {{
        background: {c.ACCENT};
        width: 16px;
        height: 16px;
        margin: -6px 0;
        border-radius: 8px;
    }}

    QSlider::handle:horizontal:hover {{
        background: {c.ACCENT_2};
    }}

    QSlider::sub-page:horizontal {{
        background: {c.ACCENT};
        border-radius: 2px;
    }}

    /* ── ComboBox ── */

    QComboBox {{
        background: {c.PAPER_3};
        color: {c.INK};
        border: 1px solid {c.RULE};
        border-radius: 8px;
        padding: 7px 10px;
        font-size: 13px;
        min-width: 80px;
    }}

    QComboBox:hover {{
        border-color: {c.MUTE_2};
    }}

    QComboBox:focus {{
        border-color: {c.ACCENT};
    }}

    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        border: none;
        width: 28px;
        background: transparent;
    }}

    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {c.MUTE};
        margin-right: 8px;
    }}

    QComboBox QAbstractItemView {{
        background: {c.PAPER_3};
        color: {c.INK};
        border: 1px solid {c.RULE};
        border-radius: 8px;
        padding: 4px;
        selection-background-color: {c.ACCENT_SOFT};
        selection-color: {c.ACCENT_2};
        outline: none;
    }}

    QComboBox QAbstractItemView::item {{
        padding: 6px 10px;
        border-radius: 4px;
        min-height: 20px;
    }}

    QComboBox QAbstractItemView::item:selected {{
        background: {c.ACCENT_SOFT};
        color: {c.ACCENT_2};
    }}

    /* ── Tooltip ── */

    QToolTip {{
        background: {c.INK};
        color: {c.PAPER_3};
        border: none;
        border-radius: 4px;
        padding: 5px 8px;
        font-size: 12px;
    }}

    /* ── Frames / Separators ── */

    QFrame[role="separator"] {{
        background: {c.RULE};
        max-height: 1px;
    }}

    QFrame[role="card"] {{
        background: {c.PAPER_2};
        border: 1px solid {c.RULE};
        border-radius: 10px;
    }}
    """


# ---------------------------------------------------------------------------
# Font resolution. The design names DM Sans / Instrument Serif / JetBrains
# Mono, which most Windows machines don't have. Any .ttf/.otf dropped into
# resources/fonts is registered, then each role falls back to the first
# installed family from its preference list. Must run after QApplication
# exists and before any widget is built.
# ---------------------------------------------------------------------------

_FONT_PREFS = {
    "BODY": ["DM Sans", "Inter", "Segoe UI Variable Text", "Segoe UI", "Arial"],
    "SERIF": ["Instrument Serif", "Georgia", "Cambria", "Times New Roman"],
    "MONO": ["JetBrains Mono", "Cascadia Code", "Cascadia Mono", "Consolas", "Courier New"],
}


def resolve_fonts() -> dict:
    """Register bundled fonts and pick installed fallbacks for each role."""
    import os
    from PySide6.QtGui import QFontDatabase

    fonts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "resources", "fonts")
    if os.path.isdir(fonts_dir):
        for name in os.listdir(fonts_dir):
            if name.lower().endswith((".ttf", ".otf")):
                QFontDatabase.addApplicationFont(os.path.join(fonts_dir, name))

    installed = set(QFontDatabase.families())
    chosen = {}
    for role, prefs in _FONT_PREFS.items():
        pick = next((f for f in prefs if f in installed), prefs[-1])
        setattr(Fonts, role, pick)
        chosen[role] = pick
    return chosen
