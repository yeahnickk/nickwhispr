from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QScrollArea, QFrame, QGridLayout, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor

from whisprnick.ui.widgets.card import Card
from whisprnick.ui.widgets.scroll_safe import NoWheelSlider
from whisprnick.ui.widgets.field_label import FieldLabel
from whisprnick.ui.widgets.section_title import SectionTitle
from whisprnick.ui.widgets.icons import icon_label
from whisprnick.ui.styles.theme import Colors, Fonts


def _format_duration(seconds: int) -> str:
    if seconds >= 60:
        m = seconds // 60
        s = seconds % 60
        return f"{m}m {s}s" if s else f"{m}m"
    return f"{seconds}s"


class SafeguardsPage(QWidget):
    settings_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(28, 28, 28, 28)
        main_layout.setSpacing(0)

        header = SectionTitle(
            "Safeguards",
            "The 'don't accidentally leave the mic on for 5 hours' department.",
        )
        main_layout.addWidget(header)

        grid = QGridLayout()
        grid.setSpacing(14)

        # --- Card 1: Max recording length ---
        c1 = Card(padded=True)
        c1_lay = QVBoxLayout(c1)
        c1_lay.setContentsMargins(0, 0, 0, 0)
        c1_lay.setSpacing(0)

        c1_title = FieldLabel("Max recording length")
        c1_lay.addWidget(c1_title)
        c1_lay.addSpacing(8)

        self._max_len_label = QLabel("1m", self)
        self._max_len_label.setStyleSheet(
            f"font-family: \"{Fonts.SERIF}\"; font-size: 38px; color: {Colors.INK}; background: transparent;"
        )
        c1_lay.addWidget(self._max_len_label)

        c1_desc = QLabel("Hard cap. Recording stops automatically.", self)
        c1_desc.setWordWrap(True)
        c1_desc.setStyleSheet(
            f"font-size: 12px; color: {Colors.MUTE}; background: transparent;"
        )
        c1_lay.addWidget(c1_desc)
        c1_lay.addSpacing(18)

        self._max_len_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self._max_len_slider.setMinimum(15)
        self._max_len_slider.setMaximum(600)
        self._max_len_slider.setSingleStep(15)
        self._max_len_slider.setPageStep(15)
        self._max_len_slider.setValue(60)
        self._max_len_slider.valueChanged.connect(self._on_max_len_changed)
        c1_lay.addWidget(self._max_len_slider)

        range_row = QHBoxLayout()
        lo = QLabel("15s", self)
        lo.setStyleSheet(f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; background: transparent;")
        hi = QLabel("10m", self)
        hi.setStyleSheet(f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; background: transparent;")
        hi.setAlignment(Qt.AlignmentFlag.AlignRight)
        range_row.addWidget(lo)
        range_row.addStretch()
        range_row.addWidget(hi)
        c1_lay.addLayout(range_row)
        c1_lay.addSpacing(16)

        grid.addWidget(c1, 0, 0)

        # --- Card 2: Silence cutoff ---
        c2 = Card(padded=True)
        c2_lay = QVBoxLayout(c2)
        c2_lay.setContentsMargins(0, 0, 0, 0)
        c2_lay.setSpacing(0)

        c2_title = FieldLabel("Silence cutoff")
        c2_lay.addWidget(c2_title)
        c2_lay.addSpacing(8)

        self._idle_label = QLabel("3s", self)
        self._idle_label.setStyleSheet(
            f"font-family: \"{Fonts.SERIF}\"; font-size: 38px; color: {Colors.INK}; background: transparent;"
        )
        c2_lay.addWidget(self._idle_label)

        c2_desc = QLabel("Stop if I haven't said anything for this long.", self)
        c2_desc.setWordWrap(True)
        c2_desc.setStyleSheet(
            f"font-size: 12px; color: {Colors.MUTE}; background: transparent;"
        )
        c2_lay.addWidget(c2_desc)
        c2_lay.addSpacing(18)

        self._idle_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self._idle_slider.setMinimum(1)
        self._idle_slider.setMaximum(15)
        self._idle_slider.setValue(3)
        self._idle_slider.valueChanged.connect(self._on_idle_changed)
        c2_lay.addWidget(self._idle_slider)

        range_row2 = QHBoxLayout()
        lo2 = QLabel("1s", self)
        lo2.setStyleSheet(f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; background: transparent;")
        hi2 = QLabel("15s", self)
        hi2.setStyleSheet(f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; background: transparent;")
        hi2.setAlignment(Qt.AlignmentFlag.AlignRight)
        range_row2.addWidget(lo2)
        range_row2.addStretch()
        range_row2.addWidget(hi2)
        c2_lay.addLayout(range_row2)
        c2_lay.addSpacing(16)

        grid.addWidget(c2, 0, 1)

        main_layout.addLayout(grid)
        main_layout.addSpacing(14)

        # --- Info banner ---
        banner = Card(padded=True)
        banner.setStyleSheet(
            "Card { background: #e4eed8; border: 1px solid #c5dab2; "
            "border-radius: 14px; padding: 18px; }"
        )
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(0, 0, 0, 0)
        banner_layout.setSpacing(12)

        shield_bg = QWidget(self)
        shield_bg.setFixedSize(32, 32)
        shield_bg.setStyleSheet(
            "background: #c5dab2; border-radius: 16px; border: none;"
        )
        shield_icon = icon_label("shield", 16, "#2e4a1e")
        shield_icon.setParent(shield_bg)
        shield_icon.move(8, 8)
        banner_layout.addWidget(shield_bg, 0, Qt.AlignmentFlag.AlignTop)

        self._warning_label = QLabel(self)
        self._warning_label.setWordWrap(True)
        self._warning_label.setStyleSheet(
            "font-size: 13px; color: #2e4a1e; background: transparent; border: none;"
        )
        self._update_warning_text()
        banner_layout.addWidget(self._warning_label, 1)

        main_layout.addWidget(banner)
        main_layout.addStretch()

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _on_max_len_changed(self, value: int):
        snapped = round(value / 15) * 15
        if snapped != value:
            self._max_len_slider.setValue(snapped)
            return
        self._max_len_label.setText(_format_duration(snapped))
        self._update_warning_text()
        self._emit_settings()

    def _on_idle_changed(self, value: int):
        self._idle_label.setText(f"{value}s")
        self._emit_settings()

    def _update_warning_text(self):
        max_sec = self._max_len_slider.value()
        duration = _format_duration(max_sec)
        self._warning_label.setText(
            f"<b>100% local.</b> Everything runs on your machine — no cloud, no API keys, "
            f"no costs. A runaway recording maxes out at <b>{duration}</b> and stops. "
            f"You're fine."
        )

    def _emit_settings(self):
        self.settings_changed.emit(self.get_settings())

    def set_settings(self, settings):
        if hasattr(settings, "max_recording_seconds"):
            self._max_len_slider.setValue(settings.max_recording_seconds)
        if hasattr(settings, "silence_cutoff_seconds"):
            self._idle_slider.setValue(settings.silence_cutoff_seconds)

    def get_settings(self) -> dict:
        return {
            "max_recording_seconds": self._max_len_slider.value(),
            "silence_cutoff_seconds": self._idle_slider.value(),
        }
