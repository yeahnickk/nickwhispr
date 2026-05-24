from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame,
    QLineEdit, QScrollArea, QSizePolicy, QTextBrowser,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

from whisprnick.ui.widgets.btn import Btn
from whisprnick.ui.widgets.pill import Pill
from whisprnick.ui.widgets.field_label import FieldLabel
from whisprnick.ui.styles.theme import Colors, Fonts


class _HistoryItem(QWidget):
    clicked = Signal(int)

    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self._id = entry.get("id", 0)
        self._active = False
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._apply_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel(entry.get("title", ""), self)
        title_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {Colors.INK}; background: transparent;"
        )
        fm = title_lbl.fontMetrics()
        title_lbl.setText(fm.elidedText(entry.get("title", ""), Qt.TextElideMode.ElideRight, 220))
        top_row.addWidget(title_lbl, 1)

        dur_lbl = QLabel(entry.get("dur", ""), self)
        dur_lbl.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 10.5px; color: {Colors.MUTE}; background: transparent;"
        )
        top_row.addWidget(dur_lbl)
        layout.addLayout(top_row)

        body_lbl = QLabel(entry.get("body", ""), self)
        body_lbl.setStyleSheet(
            f"font-size: 11.5px; color: {Colors.MUTE}; background: transparent;"
        )
        fm2 = body_lbl.fontMetrics()
        body_lbl.setText(fm2.elidedText(entry.get("body", ""), Qt.TextElideMode.ElideRight, 300))
        layout.addWidget(body_lbl)

    def _apply_style(self):
        if self._active:
            self.setStyleSheet(
                f"_HistoryItem {{ background: {Colors.PAPER_3}; border-radius: 8px; "
                f"border: 1px solid {Colors.RULE}; }}"
            )
        else:
            self.setStyleSheet(
                f"_HistoryItem {{ background: transparent; border-radius: 8px; border: none; }} "
                f"_HistoryItem:hover {{ background: {Colors.PAPER_3}; }}"
            )

    def set_active(self, active: bool):
        self._active = active
        self._apply_style()

    def mousePressEvent(self, event):
        self.clicked.emit(self._id)


class HistoryPage(QWidget):
    entry_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {Colors.PAPER};")

        self._entries: list[dict] = []
        self._items: list[_HistoryItem] = []
        self._selected_id: int | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        left_panel = QWidget(self)
        left_panel.setFixedWidth(340)
        left_panel.setStyleSheet(
            f"background: {Colors.PAPER}; border-right: 1px solid {Colors.RULE};"
        )

        left_outer = QVBoxLayout(left_panel)
        left_outer.setContentsMargins(14, 20, 14, 14)
        left_outer.setSpacing(0)

        header_widget = QWidget(self)
        header_widget.setStyleSheet("background: transparent;")
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(6, 0, 6, 12)
        header_layout.setSpacing(12)

        title_lbl = QLabel("History", self)
        title_lbl.setStyleSheet(
            f"font-family: \"{Fonts.SERIF}\"; font-size: 28px; "
            f"letter-spacing: -0.3px; color: {Colors.INK}; background: transparent;"
        )
        header_layout.addWidget(title_lbl)

        search_container = QWidget(self)
        search_container.setStyleSheet("background: transparent;")
        search_inner = QHBoxLayout(search_container)
        search_inner.setContentsMargins(0, 0, 0, 0)
        search_inner.setSpacing(0)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Search transcripts…")
        self._search.setStyleSheet(
            f"QLineEdit {{ background: {Colors.PAPER_3}; border: 1px solid {Colors.RULE}; "
            f"border-radius: 9px; padding: 8px 10px 8px 32px; font-size: 13px; color: {Colors.INK}; }}"
        )
        self._search.textChanged.connect(self._on_search)
        search_inner.addWidget(self._search)
        header_layout.addWidget(search_container)

        left_outer.addWidget(header_widget)

        self._list_scroll = QScrollArea(self)
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )
        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()
        self._list_scroll.setWidget(self._list_widget)
        left_outer.addWidget(self._list_scroll, 1)
        root.addWidget(left_panel)

        self._detail_scroll = QScrollArea(self)
        self._detail_scroll.setWidgetResizable(True)
        self._detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._detail_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )
        self._detail_widget = QWidget()
        self._detail_widget.setStyleSheet(f"background: {Colors.PAPER};")
        self._detail_layout = QVBoxLayout(self._detail_widget)
        self._detail_layout.setContentsMargins(28, 28, 28, 28)
        self._detail_layout.setSpacing(0)

        top_section = QHBoxLayout()
        top_section.setSpacing(0)

        info_col = QVBoxLayout()
        info_col.setSpacing(0)

        self._pills_row = QHBoxLayout()
        self._pills_row.setSpacing(8)
        self._pill_target = Pill("", tone="paper")
        self._pill_dur = Pill("", tone="default", icon_name="clock")
        self._pill_words = Pill("", tone="default")
        self._pill_fillers = Pill("", tone="good", icon_name="sparkle")
        self._pills_row.addWidget(self._pill_target)
        self._pills_row.addWidget(self._pill_dur)
        self._pills_row.addWidget(self._pill_words)
        self._pills_row.addWidget(self._pill_fillers)
        self._pills_row.addStretch()
        info_col.addLayout(self._pills_row)
        info_col.addSpacing(8)

        self._detail_title = QLabel("", self)
        self._detail_title.setWordWrap(True)
        self._detail_title.setStyleSheet(
            f"font-family: \"{Fonts.SERIF}\"; font-size: 24px; "
            f"letter-spacing: -0.3px; color: {Colors.INK}; background: transparent;"
        )
        info_col.addWidget(self._detail_title)
        info_col.addSpacing(4)

        self._detail_when = QLabel("", self)
        self._detail_when.setWordWrap(True)
        self._detail_when.setStyleSheet(
            f"font-size: 12px; color: {Colors.MUTE}; background: transparent;"
        )
        info_col.addWidget(self._detail_when)
        top_section.addLayout(info_col, 1)

        btn_col = QHBoxLayout()
        btn_col.setSpacing(6)

        self._copy_btn = Btn("Copy", variant="outline", size="sm", icon_name="copy")
        self._copy_btn.clicked.connect(self._on_copy)
        btn_col.addWidget(self._copy_btn)

        top_section.addLayout(btn_col)
        self._detail_layout.addLayout(top_section)
        self._detail_layout.addSpacing(22)

        transcript_col = QVBoxLayout()
        transcript_col.setSpacing(8)
        transcript_label = FieldLabel("Transcript")
        transcript_col.addWidget(transcript_label)

        self._clean_browser = QTextBrowser(self)
        self._clean_browser.setOpenLinks(False)
        from PySide6.QtGui import QTextOption
        self._clean_browser.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self._clean_browser.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        self._clean_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._clean_browser.setStyleSheet(
            f"QTextBrowser {{ background: {Colors.PAPER_3}; border: 1px solid {Colors.RULE}; "
            f"border-radius: 12px; padding: 16px; font-size: 14px; color: {Colors.INK}; }}"
        )
        self._clean_browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._clean_browser.setMinimumHeight(150)
        transcript_col.addWidget(self._clean_browser, 1)

        self._raw_browser = self._clean_browser

        self._detail_layout.addLayout(transcript_col, 1)
        self._detail_layout.addSpacing(22)

        self._model_footer = QLabel("", self)
        self._model_footer.setWordWrap(True)
        self._model_footer.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; background: transparent;"
        )
        self._detail_layout.addWidget(self._model_footer)

        self._detail_scroll.setWidget(self._detail_widget)
        root.addWidget(self._detail_scroll, 1)

        # -- Empty-state message for the left panel list --
        self._empty_list_label = QLabel(
            "No dictations yet.\nPress Ctrl+Shift+Space to start.", self
        )
        self._empty_list_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_list_label.setWordWrap(True)
        self._empty_list_label.setStyleSheet(
            f"font-size: 13px; color: {Colors.MUTE}; background: transparent; padding: 40px 20px;"
        )
        self._empty_list_label.hide()

        # Show no-selection state on launch
        self._show_detail_empty_state()

    def _show_detail_empty_state(self):
        """Hide detail controls and show friendly placeholder when nothing is selected."""
        self._pill_target.hide()
        self._pill_dur.hide()
        self._pill_words.hide()
        self._pill_fillers.hide()
        self._detail_title.hide()
        self._detail_when.hide()
        self._copy_btn.hide()
        self._model_footer.hide()

        self._raw_browser.setHtml(
            f'<div style="font-family: \'{Fonts.BODY}\'; font-size: 14px; '
            f'line-height: 1.6; color: {Colors.MUTE}; text-align: center; '
            f'padding-top: 40px;">No dictation selected</div>'
        )
        self._clean_browser.setHtml(
            f'<div style="font-family: \'{Fonts.BODY}\'; font-size: 14px; '
            f'line-height: 1.6; color: {Colors.MUTE}; text-align: center; '
            f'padding-top: 40px;">Your transcripts will appear here</div>'
        )

    def _show_detail_controls(self):
        """Show detail controls when an entry is selected."""
        self._pill_target.show()
        self._pill_dur.show()
        self._pill_words.show()
        # _pill_fillers visibility is set per-entry in select_entry
        self._detail_title.show()
        self._detail_when.show()
        self._copy_btn.show()
        self._model_footer.show()

    def _on_search(self, text: str):
        text_lower = text.lower()
        for item in self._items:
            entry = next((e for e in self._entries if e.get("id") == item._id), None)
            if entry is None:
                continue
            visible = (
                not text_lower
                or text_lower in entry.get("title", "").lower()
                or text_lower in entry.get("body", "").lower()
                or text_lower in entry.get("raw", "").lower()
            )
            item.setVisible(visible)

    def _on_copy(self):
        if self._selected_id is None:
            return
        entry = next((e for e in self._entries if e.get("id") == self._selected_id), None)
        if entry:
            from PySide6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(entry.get("body", ""))

    def _clear_list(self):
        for item in self._items:
            item.deleteLater()
        self._items.clear()

        while self._list_layout.count():
            child = self._list_layout.takeAt(0)
            if child.widget() and child.widget() not in self._items:
                child.widget().deleteLater()

    def set_entries(self, entries: list):
        self._entries = entries
        self._selected_id = None
        self._clear_list()

        self._list_layout = QVBoxLayout()
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)

        list_widget = QWidget()
        list_widget.setStyleSheet("background: transparent;")
        list_widget.setLayout(self._list_layout)

        if not entries:
            # Show empty-state message in left panel
            self._empty_list_label.show()
            self._list_layout.addWidget(self._empty_list_label)
            self._list_layout.addStretch()
            self._list_scroll.setWidget(list_widget)
            self._show_detail_empty_state()
            return

        self._empty_list_label.hide()

        groups: dict[str, list[dict]] = {}
        for entry in entries:
            group = entry.get("group", "Today")
            if group not in groups:
                groups[group] = []
            groups[group].append(entry)

        for group_name, group_entries in groups.items():
            group_lbl = QLabel(group_name, self)
            group_lbl.setStyleSheet(
                f"font-size: 11px; color: {Colors.MUTE}; text-transform: uppercase; "
                f"letter-spacing: 0.8px; padding: 10px 8px 6px; background: transparent;"
            )
            self._list_layout.addWidget(group_lbl)

            for entry in group_entries:
                item = _HistoryItem(entry, self)
                item.clicked.connect(self._on_item_clicked)
                self._items.append(item)
                self._list_layout.addWidget(item)

        self._list_layout.addStretch()
        self._list_scroll.setWidget(list_widget)

        if entries:
            self.select_entry(entries[0].get("id", 0))

    def _on_item_clicked(self, entry_id: int):
        self.select_entry(entry_id)
        self.entry_selected.emit(entry_id)

    def select_entry(self, entry_id: int):
        self._selected_id = entry_id

        for item in self._items:
            item.set_active(item._id == entry_id)

        entry = next((e for e in self._entries if e.get("id") == entry_id), None)
        if entry is None:
            self._show_detail_empty_state()
            return

        self._show_detail_controls()

        self._pill_target.setText(entry.get("target", ""))
        self._pill_dur.setText(entry.get("dur", ""))
        self._pill_words.setText(f"{entry.get('words', 0)} words")

        trims = entry.get("trims", [])
        if trims:
            self._pill_fillers.setText(f"{len(trims)} fillers trimmed")
            self._pill_fillers.show()
        else:
            self._pill_fillers.hide()

        self._detail_title.setText(entry.get("title", ""))
        self._detail_when.setText(entry.get("when", ""))

        self._clean_browser.setHtml(
            f'<div style="font-family: \'{Fonts.BODY}\'; font-size: 14px; '
            f'line-height: 1.6; color: {Colors.INK};">{entry.get("body", "")}</div>'
        )

        whisper_model = entry.get("whisper_model", "small")
        cleanup_model = entry.get("cleanup_model", "qwen2.5:3b")
        latency = entry.get("latency_ms", 0)
        self._model_footer.setText(
            f"WHISPER · {whisper_model}   CLEANUP · {cleanup_model}   "
            f"LAT · {latency}ms"
        )

