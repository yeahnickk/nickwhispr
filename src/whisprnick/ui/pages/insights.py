from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame,
    QScrollArea, QSizePolicy, QGridLayout,
)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QBrush, QPen

from whisprnick.ui.widgets.card import Card
from whisprnick.ui.widgets.btn import Btn
from whisprnick.ui.widgets.pill import Pill
from whisprnick.ui.widgets.field_label import FieldLabel
from whisprnick.ui.widgets.section_title import SectionTitle
from whisprnick.ui.widgets.stat import BigStat
from whisprnick.ui.widgets.icons import icon_pixmap, icon_label
from whisprnick.ui.styles.theme import Colors, Fonts


def _separator(parent=None) -> QFrame:
    line = QFrame(parent)
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"background: {Colors.RULE}; border: none; max-height: 1px;")
    line.setFixedHeight(1)
    return line


class _BarChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._values: list[float] = [0] * 7
        self._labels = ["M", "T", "W", "T", "F", "S", "S"]
        self._highlight_index: int | None = None
        self.setMinimumHeight(160)
        self.setStyleSheet("background: transparent;")

    def set_values(self, values: list[float], highlight_index: int | None = None):
        self._values = values[:7] if len(values) >= 7 else values + [0] * (7 - len(values))
        self._highlight_index = highlight_index
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        label_h = 24
        chart_h = h - label_h
        padding_x = 6
        bar_area_w = w - padding_x * 2

        max_val = max(self._values) if any(v > 0 for v in self._values) else 1
        bar_count = len(self._values)
        gap = 14
        bar_w = max(8, (bar_area_w - gap * (bar_count - 1)) / bar_count)

        for i, val in enumerate(self._values):
            x = padding_x + i * (bar_w + gap)
            bar_h = max(2, (val / max_val) * chart_h * 0.9) if max_val > 0 else 2
            y = chart_h - bar_h

            if self._highlight_index is not None and i == self._highlight_index:
                color = QColor(Colors.ACCENT)
            else:
                color = QColor(Colors.INK)
                color.setAlphaF(0.85)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 6, 6)

            p.setPen(QColor(Colors.MUTE))
            from PySide6.QtGui import QFont
            font = QFont(Fonts.MONO, 9)
            p.setFont(font)
            label_x = x + bar_w / 2
            p.drawText(
                QRectF(x - 4, chart_h + 4, bar_w + 8, label_h),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                self._labels[i] if i < len(self._labels) else "",
            )

        p.end()


class _BarTrack(QWidget):
    def __init__(self, percentage: int, color: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(6)
        self._pct = percentage
        self._color = color

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(Colors.RULE_2))
        p.drawRoundedRect(QRectF(0, 0, self.width(), 6), 3, 3)
        fill_w = max(2, self.width() * self._pct / 100)
        p.setBrush(QColor(self._color))
        p.drawRoundedRect(QRectF(0, 0, fill_w, 6), 3, 3)
        p.end()


class _AppBreakdownBar(QWidget):
    def __init__(self, app_name: str, percentage: int, color: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        top = QHBoxLayout()
        name_lbl = QLabel(app_name, self)
        name_lbl.setStyleSheet(f"font-size: 12px; color: {Colors.INK}; background: transparent;")
        top.addWidget(name_lbl)
        top.addStretch()
        pct_lbl = QLabel(f"{percentage}%", self)
        pct_lbl.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; background: transparent;"
        )
        top.addWidget(pct_lbl)
        layout.addLayout(top)

        layout.addWidget(_BarTrack(percentage, color, self))


class _CrutchChip(QWidget):
    def __init__(self, word: str, count: int, inverted: bool = False, parent=None):
        super().__init__(parent)

        if inverted:
            bg = Colors.INK
            fg = Colors.PAPER
            border_color = Colors.INK
        else:
            bg = Colors.PAPER_3
            fg = Colors.INK_2
            border_color = Colors.RULE

        self.setStyleSheet(
            f"_CrutchChip {{ background: {bg}; border: 1px solid {border_color}; "
            f"border-radius: 999px; padding: 8px 12px; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        word_lbl = QLabel(f'"{word}"', self)
        word_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {fg}; background: transparent; border: none; padding: 0;"
        )
        layout.addWidget(word_lbl)

        count_lbl = QLabel(f"×{count}", self)
        opacity = "0.65"
        count_lbl.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {fg}; "
            f"opacity: {opacity}; background: transparent; border: none; padding: 0;"
        )
        layout.addWidget(count_lbl)


class _FlowLayout(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._widgets: list[QWidget] = []

    def add_widget(self, widget: QWidget):
        widget.setParent(self)
        self._widgets.append(widget)
        self._relayout()

    def clear_widgets(self):
        for w in self._widgets:
            w.deleteLater()
        self._widgets.clear()

    def _relayout(self):
        if not self._widgets:
            return
        x = 0
        y = 0
        row_height = 0
        spacing = 8
        width = max(self.width(), 200)

        for w in self._widgets:
            w.adjustSize()
            ww = w.sizeHint().width()
            wh = w.sizeHint().height()
            if x + ww > width and x > 0:
                x = 0
                y += row_height + spacing
                row_height = 0
            w.move(x, y)
            w.show()
            x += ww + spacing
            row_height = max(row_height, wh)

        self.setMinimumHeight(y + row_height + 4)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()


class InsightsPage(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            f"QScrollArea {{ background: {Colors.PAPER}; border: none; }}"
        )

        content = QWidget()
        content.setStyleSheet(f"background: {Colors.PAPER};")
        self.setWidget(content)

        root = QVBoxLayout(content)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(14)

        self._section_title = SectionTitle(
            title="Insights",
            subtitle="A friendly look at your week — no judgement, mostly.",
        )
        root.addWidget(self._section_title)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(14)

        self._stat_words = BigStat(value="0", label="words", sub="this week")
        self._stat_time = BigStat(value="0m", label="time saved", sub="vs typing at 40 wpm")
        self._stat_fillers = BigStat(value="0", label="fillers trimmed", sub="")

        stats_row.addWidget(self._stat_words, 1)
        stats_row.addWidget(self._stat_time, 1)
        stats_row.addWidget(self._stat_fillers, 1)
        root.addLayout(stats_row)

        mid_row = QHBoxLayout()
        mid_row.setSpacing(14)

        activity_card = Card(parent=self)
        act_layout = QVBoxLayout(activity_card)
        act_layout.setContentsMargins(0, 0, 0, 0)
        act_layout.setSpacing(0)

        act_header = QHBoxLayout()
        act_label = FieldLabel("Activity this week")
        act_header.addWidget(act_label)
        act_header.addStretch()
        act_unit = QLabel("minutes recorded", self)
        act_unit.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; background: transparent;"
        )
        act_header.addWidget(act_unit)
        act_layout.addLayout(act_header)
        act_layout.addSpacing(18)

        self._chart = _BarChartWidget(self)
        self._chart.setMinimumHeight(160)
        act_layout.addWidget(self._chart, 1)

        mid_row.addWidget(activity_card, 14)

        app_card = Card(parent=self)
        app_layout = QVBoxLayout(app_card)
        app_layout.setContentsMargins(0, 0, 0, 0)
        app_layout.setSpacing(10)

        app_label = FieldLabel("Where it went")
        app_layout.addWidget(app_label)
        app_layout.addSpacing(4)

        self._app_breakdown_layout = QVBoxLayout()
        self._app_breakdown_layout.setSpacing(10)
        app_layout.addLayout(self._app_breakdown_layout)
        app_layout.addStretch()

        mid_row.addWidget(app_card, 10)
        root.addLayout(mid_row)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(14)

        crutch_card = Card(parent=self)
        crutch_layout = QVBoxLayout(crutch_card)
        crutch_layout.setContentsMargins(0, 0, 0, 0)
        crutch_layout.setSpacing(0)

        crutch_label = FieldLabel("Your top crutch words")
        crutch_layout.addWidget(crutch_label)
        crutch_layout.addSpacing(4)

        crutch_sub = QLabel("We trimmed these for you. You're welcome.", self)
        crutch_sub.setWordWrap(True)
        crutch_sub.setStyleSheet(
            f"font-size: 12px; color: {Colors.MUTE}; background: transparent;"
        )
        crutch_layout.addWidget(crutch_sub)
        crutch_layout.addSpacing(14)

        self._crutch_flow = _FlowLayout(self)
        crutch_layout.addWidget(self._crutch_flow, 1)

        bottom_row.addWidget(crutch_card, 1)

        # Local-only info card (replaces cost breakdown)
        local_card = Card(parent=self)
        local_layout = QVBoxLayout(local_card)
        local_layout.setContentsMargins(0, 0, 0, 0)
        local_layout.setSpacing(10)

        local_label = FieldLabel("Running locally")
        local_layout.addWidget(local_label)
        local_layout.addSpacing(4)

        local_desc = QLabel(self)
        local_desc.setWordWrap(True)
        local_desc.setTextFormat(Qt.TextFormat.RichText)
        local_desc.setStyleSheet(
            f"font-size: 13px; color: {Colors.INK_2}; line-height: 170%; background: transparent;"
        )
        local_desc.setText(
            f"Both Whisper and Qwen run entirely on your machine. "
            f"No cloud APIs, no subscriptions, no per-minute fees. "
            f'<br><br><b style="color: {Colors.GOOD};">Total cost: free.</b>'
        )
        local_layout.addWidget(local_desc)
        local_layout.addStretch()

        bottom_row.addWidget(local_card, 1)
        root.addLayout(bottom_row)

        root.addStretch()

        self._load_sample_data()

    def _load_sample_data(self):
        self.update_stats(0, 0, 0)
        self.update_activity([0, 0, 0, 0, 0, 0, 0])
        self.update_app_usage([])
        self.update_top_fillers([])

    def update_stats(self, words: int, time_saved_min: float, fillers: int):
        self._stat_words.set_value(f"{words:,}")
        hours = int(time_saved_min // 60)
        mins = int(time_saved_min % 60)
        if hours > 0:
            self._stat_time.set_value(f"{hours}h {mins}m")
        else:
            self._stat_time.set_value(f"{mins}m")
        self._stat_fillers.set_value(f"{fillers:,}")

    def update_activity(self, daily_minutes: list[float], highlight_index: int | None = None):
        self._chart.set_values(daily_minutes, highlight_index=highlight_index)

    def update_app_usage(self, apps: list[tuple[str, int]]):
        while self._app_breakdown_layout.count():
            item = self._app_breakdown_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        app_colors = [Colors.INK, "#4a3a5a", Colors.ACCENT, Colors.WARN, Colors.MUTE_2]
        for i, (app_name, percentage) in enumerate(apps):
            color = app_colors[i] if i < len(app_colors) else Colors.MUTE_2
            bar = _AppBreakdownBar(app_name, percentage, color, self)
            self._app_breakdown_layout.addWidget(bar)

    def update_top_fillers(self, fillers: list[tuple[str, int]]):
        self._crutch_flow.clear_widgets()
        for i, (word, count) in enumerate(fillers):
            chip = _CrutchChip(word, count, inverted=(i == 0), parent=self._crutch_flow)
            self._crutch_flow.add_widget(chip)
