from __future__ import annotations

from datetime import date, datetime

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame,
    QScrollArea, QGridLayout, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QFont

from whisprnick.ui.widgets.card import Card
from whisprnick.ui.widgets.field_label import FieldLabel
from whisprnick.ui.widgets.section_title import SectionTitle
from whisprnick.ui.widgets.stat import BigStat
from whisprnick.ui.styles.theme import Colors, Fonts

# (setting value, label, chart span in days)
PERIODS = [(7, "7 days", 7), (30, "30 days", 30), (None, "All time", 30)]


def _fmt_minutes(total_min: float) -> str:
    total_min = int(round(total_min))
    if total_min >= 60:
        return f"{total_min // 60}h {total_min % 60}m"
    return f"{total_min}m"


def _fmt_hour(h: int) -> str:
    suffix = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}{suffix}"


class _PeriodButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setStyleSheet(
            f"_PeriodButton {{ padding: 6px 12px; border: none; border-radius: 7px; font-size: 12.5px; "
            f"color: {Colors.MUTE}; background: transparent; font-family: \"{Fonts.BODY}\"; }}"
            f"_PeriodButton:checked {{ background: {Colors.PAPER_3}; color: {Colors.INK}; font-weight: 500; }}"
        )


class _BarChartWidget(QWidget):
    """Daily words as bars. Value labels appear when there is room."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values: list[float] = [0.0] * 7
        self._labels: list[str] = [""] * 7
        self._highlight: int | None = None
        self._empty_text = "No dictations in this period yet."
        self.setMinimumHeight(170)
        self.setStyleSheet("background: transparent;")

    def set_series(self, values: list[float], labels: list[str], highlight_index: int | None = None):
        self._values = list(values)
        self._labels = list(labels)
        self._highlight = highlight_index
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        label_h = 22
        value_h = 16
        chart_top = value_h
        chart_h = h - label_h - value_h
        n = max(1, len(self._values))
        max_val = max(self._values) if any(v > 0 for v in self._values) else 0

        if max_val == 0:
            p.setPen(QColor(Colors.MUTE_2))
            p.setFont(QFont(Fonts.BODY, 10))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._empty_text)
            p.end()
            return

        gap = 12 if n <= 7 else 4
        bar_w = max(4.0, (w - gap * (n - 1)) / n)
        show_values = n <= 14
        p.setFont(QFont(Fonts.MONO, 8 if n > 7 else 9))

        for i, val in enumerate(self._values):
            x = i * (bar_w + gap)
            bar_h = max(2.0, (val / max_val) * chart_h) if val > 0 else 2.0
            y = chart_top + chart_h - bar_h
            if self._highlight is not None and i == self._highlight:
                color = QColor(Colors.ACCENT)
            else:
                color = QColor(Colors.INK)
                color.setAlphaF(0.85 if val > 0 else 0.15)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(x, y, bar_w, bar_h), min(6.0, bar_w / 2), min(6.0, bar_w / 2))

            p.setPen(QColor(Colors.MUTE))
            if show_values and val > 0:
                p.drawText(QRectF(x - 10, y - value_h, bar_w + 20, value_h),
                           Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, f"{int(val):,}")
            label = self._labels[i] if i < len(self._labels) else ""
            if label:
                p.drawText(QRectF(x - 10, chart_top + chart_h + 4, bar_w + 20, label_h),
                           Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)
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
    def __init__(self, app_name: str, percentage: int, words: int, color: str, parent=None):
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
        pct_lbl = QLabel(f"{words:,} · {percentage}%", self)
        pct_lbl.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; background: transparent;"
        )
        top.addWidget(pct_lbl)
        layout.addLayout(top)
        layout.addWidget(_BarTrack(percentage, color, self))


class _CrutchChip(QWidget):
    def __init__(self, word: str, count: int, inverted: bool = False, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        if inverted:
            bg, fg, border = Colors.INK, Colors.PAPER, Colors.INK
        else:
            bg, fg, border = Colors.PAPER_3, Colors.INK_2, Colors.RULE
        self.setStyleSheet(
            f"_CrutchChip {{ background: {bg}; border: 1px solid {border}; border-radius: 999px; }}"
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
        count_lbl.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {fg}; background: transparent; border: none; padding: 0;"
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
            w.hide()
            w.setParent(None)
            w.deleteLater()
        self._widgets.clear()
        self.setMinimumHeight(0)

    def _relayout(self):
        if not self._widgets:
            return
        x = y = row_height = 0
        spacing = 8
        width = max(self.width(), 200)
        for w in self._widgets:
            w.adjustSize()
            ww, wh = w.sizeHint().width(), w.sizeHint().height()
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


class _Highlight(QWidget):
    """Small value + caption pair used in the Highlights grid."""

    def __init__(self, caption: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self._value = QLabel("—", self)
        self._value.setStyleSheet(
            f"font-family: \"{Fonts.SERIF}\"; font-size: 22px; color: {Colors.INK}; background: transparent;"
        )
        lay.addWidget(self._value)
        self._caption = QLabel(caption, self)
        self._caption.setWordWrap(True)
        self._caption.setStyleSheet(f"font-size: 11px; color: {Colors.MUTE}; background: transparent;")
        lay.addWidget(self._caption)

    def set(self, value: str, caption: str | None = None):
        self._value.setText(value)
        if caption is not None:
            self._caption.setText(caption)


class InsightsPage(QScrollArea):
    period_changed = Signal(object)  # days (int) or None for all time

    def __init__(self, parent=None):
        super().__init__(parent)
        self._period_days: int | None = 7
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"QScrollArea {{ background: {Colors.PAPER}; border: none; }}")

        content = QWidget()
        content.setStyleSheet(f"background: {Colors.PAPER};")
        self.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(14)

        # Period switch lives in the title row.
        switch = QFrame()
        switch.setStyleSheet(
            f"QFrame {{ background: {Colors.PAPER_2}; border: 1px solid {Colors.RULE}; border-radius: 9px; }}"
        )
        sw_lay = QHBoxLayout(switch)
        sw_lay.setContentsMargins(3, 3, 3, 3)
        sw_lay.setSpacing(2)
        self._period_buttons: list[tuple[_PeriodButton, int | None]] = []
        for value, label, _ in PERIODS:
            btn = _PeriodButton(label)
            btn.setChecked(value == self._period_days)
            btn.clicked.connect(lambda checked=False, v=value: self._on_period(v))
            sw_lay.addWidget(btn)
            self._period_buttons.append((btn, value))

        root.addWidget(SectionTitle("Insights", "A friendly look at your dictation — no judgement, mostly.",
                                    action_widget=switch))

        # Row 1: four headline numbers
        stats_row = QHBoxLayout()
        stats_row.setSpacing(14)
        self._stat_words = BigStat(value="0", label="words", sub="this week")
        self._stat_time = BigStat(value="0m", label="time saved", sub="vs typing")
        self._stat_count = BigStat(value="0", label="dictations", sub="0m recorded")
        self._stat_fillers = BigStat(value="0", label="fillers trimmed", sub="um, uh, you know…")
        for s in (self._stat_words, self._stat_time, self._stat_count, self._stat_fillers):
            stats_row.addWidget(s, 1)
        root.addLayout(stats_row)

        # Row 2: activity chart + app breakdown
        mid_row = QHBoxLayout()
        mid_row.setSpacing(14)

        activity_card = Card(parent=self)
        act_layout = QVBoxLayout(activity_card)
        act_layout.setContentsMargins(0, 0, 0, 0)
        act_layout.setSpacing(0)
        act_header = QHBoxLayout()
        act_header.addWidget(FieldLabel("Words per day"))
        act_header.addStretch()
        self._act_unit = QLabel("", self)
        self._act_unit.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; background: transparent;"
        )
        act_header.addWidget(self._act_unit)
        act_layout.addLayout(act_header)
        act_layout.addSpacing(14)
        self._chart = _BarChartWidget(self)
        act_layout.addWidget(self._chart, 1)
        mid_row.addWidget(activity_card, 14)

        app_card = Card(parent=self)
        app_layout = QVBoxLayout(app_card)
        app_layout.setContentsMargins(0, 0, 0, 0)
        app_layout.setSpacing(10)
        app_layout.addWidget(FieldLabel("Where it went"))
        self._app_breakdown_layout = QVBoxLayout()
        self._app_breakdown_layout.setSpacing(10)
        app_layout.addLayout(self._app_breakdown_layout)
        self._app_empty = QLabel("Nothing pasted yet.", self)
        self._app_empty.setStyleSheet(f"font-size: 12px; color: {Colors.MUTE_2}; background: transparent;")
        app_layout.addWidget(self._app_empty)
        app_layout.addStretch()
        mid_row.addWidget(app_card, 10)
        root.addLayout(mid_row)

        # Row 3: highlights + crutch words
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(14)

        hi_card = Card(parent=self)
        hi_layout = QVBoxLayout(hi_card)
        hi_layout.setContentsMargins(0, 0, 0, 0)
        hi_layout.setSpacing(12)
        hi_layout.addWidget(FieldLabel("Highlights"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(14)
        self._hi_best = _Highlight("best day")
        self._hi_hour = _Highlight("busiest hour")
        self._hi_pace = _Highlight("speaking pace")
        self._hi_avg = _Highlight("avg words per dictation")
        self._hi_latency = _Highlight("avg cleanup time")
        self._hi_active = _Highlight("active days")
        for i, hl in enumerate((self._hi_best, self._hi_hour, self._hi_pace,
                                self._hi_avg, self._hi_latency, self._hi_active)):
            grid.addWidget(hl, i // 3, i % 3)
        hi_layout.addLayout(grid)
        hi_layout.addStretch()
        bottom_row.addWidget(hi_card, 1)

        crutch_card = Card(parent=self)
        crutch_layout = QVBoxLayout(crutch_card)
        crutch_layout.setContentsMargins(0, 0, 0, 0)
        crutch_layout.setSpacing(0)
        crutch_layout.addWidget(FieldLabel("Your top crutch words"))
        crutch_layout.addSpacing(4)
        self._crutch_sub = QLabel("We trimmed these for you. You're welcome.", self)
        self._crutch_sub.setWordWrap(True)
        self._crutch_sub.setStyleSheet(f"font-size: 12px; color: {Colors.MUTE}; background: transparent;")
        crutch_layout.addWidget(self._crutch_sub)
        crutch_layout.addSpacing(14)
        self._crutch_flow = _FlowLayout(self)
        crutch_layout.addWidget(self._crutch_flow, 1)
        bottom_row.addWidget(crutch_card, 1)
        root.addLayout(bottom_row)
        root.addStretch()

    # ── Period ─────────────────────────────────────────────────────────

    @property
    def period_days(self) -> int | None:
        return self._period_days

    def chart_days(self) -> int:
        for value, _, span in PERIODS:
            if value == self._period_days:
                return span
        return 7

    def _on_period(self, value: int | None):
        self._period_days = value
        for btn, v in self._period_buttons:
            btn.setChecked(v == value)
        self.period_changed.emit(value)

    # ── Data in ────────────────────────────────────────────────────────

    def update_stats(self, stats: dict, wpm: int):
        period = "this week" if self._period_days == 7 else (
            "last 30 days" if self._period_days == 30 else "all time")
        words = stats.get("words", 0)
        count = stats.get("dictations", 0)
        self._stat_words.set_value(f"{words:,}")
        self._stat_words._stat._sub_lbl.setText(period)
        saved_min = words / max(wpm, 1) - stats.get("duration_seconds", 0) / 60.0
        self._stat_time.set_value(_fmt_minutes(max(0.0, saved_min)))
        self._stat_time._stat._sub_lbl.setText(f"vs typing at {wpm} wpm")
        self._stat_count.set_value(f"{count:,}")
        self._stat_count._stat._sub_lbl.setText(
            f"{_fmt_minutes(stats.get('duration_seconds', 0) / 60.0)} recorded")
        self._stat_fillers.set_value(f"{stats.get('fillers', 0):,}")
        self._stat_fillers._stat._sub_lbl.setText("um, uh, you know…")

        best = stats.get("best_day")
        if best:
            d = date.fromisoformat(best[0])
            self._hi_best.set(f"{best[1]:,}", f"best day · {d.strftime('%a %d %b')}")
        else:
            self._hi_best.set("—", "best day")
        hour = stats.get("busiest_hour")
        self._hi_hour.set(_fmt_hour(hour[0]) if hour else "—", "busiest hour")
        pace = stats.get("speaking_wpm", 0)
        self._hi_pace.set(f"{int(pace)} wpm" if pace else "—", "speaking pace")
        avg = stats.get("avg_words", 0)
        self._hi_avg.set(f"{int(round(avg))}" if avg else "—",
                         f"avg words per dictation · longest {stats.get('longest_words', 0)}")
        lat = stats.get("avg_latency_ms", 0)
        self._hi_latency.set(f"{lat} ms" if lat else "—", "avg cleanup time")
        active = stats.get("active_days", 0)
        if self._period_days:
            self._hi_active.set(f"{active}/{self._period_days}", "active days")
        else:
            self._hi_active.set(f"{active}", "active days")

    def update_activity(self, series: list[tuple[str, int, float]]):
        """series: (iso date, words, minutes), oldest first."""
        values = [float(w) for _, w, _ in series]
        n = len(series)
        labels = []
        today = date.today().isoformat()
        highlight = None
        for i, (d, _, _) in enumerate(series):
            dt = date.fromisoformat(d)
            if d == today:
                highlight = i
            if n <= 7:
                labels.append(dt.strftime("%a"))
            else:
                labels.append(dt.strftime("%d") if (i % 5 == 0 or i == n - 1) else "")
        self._chart.set_series(values, labels, highlight_index=highlight)
        total_min = sum(m for _, _, m in series)
        self._act_unit.setText(f"{_fmt_minutes(total_min)} recorded")

    def update_app_usage(self, apps: list[tuple[str, int]]):
        while self._app_breakdown_layout.count():
            item = self._app_breakdown_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        total = sum(c for _, c in apps) or 1
        colors = [Colors.INK, "#4a3a5a", Colors.ACCENT, Colors.WARN, Colors.MUTE_2]
        for i, (app_name, words) in enumerate(apps[:5]):
            color = colors[i] if i < len(colors) else Colors.MUTE_2
            self._app_breakdown_layout.addWidget(
                _AppBreakdownBar(app_name or "Unknown", int(words / total * 100), words, color, self))
        self._app_empty.setVisible(not apps)

    def update_top_fillers(self, fillers: list[tuple[str, int]]):
        self._crutch_flow.clear_widgets()
        for i, (word, count) in enumerate(fillers):
            self._crutch_flow.add_widget(_CrutchChip(word, count, inverted=(i == 0), parent=self._crutch_flow))
        self._crutch_sub.setText(
            "We trimmed these for you. You're welcome." if fillers else "Nothing trimmed yet. Clean speaker, or no dictations."
        )
