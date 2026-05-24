from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPainter, QColor

from whisprnick.ui.widgets.card import Card
from whisprnick.ui.widgets.btn import Btn
from whisprnick.ui.widgets.section_title import SectionTitle
from whisprnick.ui.widgets.icons import icon_pixmap, icon_label
from whisprnick.ui.styles.theme import Colors, Fonts


class _ConfidenceBar(QWidget):
    def __init__(self, value: int = 0, parent=None):
        super().__init__(parent)
        self._value = value
        self.setFixedSize(64, 4)

    def set_value(self, v: int):
        self._value = v
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(Colors.RULE_2))
        p.drawRoundedRect(0, 0, self.width(), self.height(), 2, 2)
        if self._value > 0:
            if self._value > 90:
                color = Colors.GOOD
            elif self._value > 80:
                color = Colors.ACCENT
            else:
                color = Colors.WARN
            w = int(self.width() * self._value / 100)
            p.setBrush(QColor(color))
            p.drawRoundedRect(0, 0, w, self.height(), 2, 2)
        p.end()


class _TabButton(QPushButton):
    def __init__(self, text: str, active: bool = False, parent=None):
        super().__init__(text, parent)
        self._active = active
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

    def set_active(self, active: bool):
        self._active = active
        self._apply_style()

    def _apply_style(self):
        if self._active:
            self.setStyleSheet(
                f"_TabButton {{ padding: 7px 14px; background: {Colors.PAPER_3}; "
                f"border: none; border-radius: 7px; font-size: 13px; color: {Colors.INK}; "
                f"font-weight: 500; font-family: \"{Fonts.BODY}\"; }}"
            )
        else:
            self.setStyleSheet(
                f"_TabButton {{ padding: 7px 14px; background: transparent; "
                f"border: none; border-radius: 7px; font-size: 13px; color: {Colors.MUTE}; "
                f"font-weight: 500; font-family: \"{Fonts.BODY}\"; }}"
            )


class _VocabRow(QWidget):
    delete_clicked = Signal()

    def __init__(self, word: str, pronunciation: str, heard: int, confidence: int, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(12)

        word_lbl = QLabel(word, self)
        word_lbl.setWordWrap(True)
        word_lbl.setStyleSheet(
            f"font-size: 13px; color: {Colors.INK}; font-weight: 500; background: transparent;"
        )
        layout.addWidget(word_lbl, 3)

        pron_lbl = QLabel(pronunciation, self)
        pron_lbl.setWordWrap(True)
        pron_lbl.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 12px; color: {Colors.MUTE}; background: transparent;"
        )
        layout.addWidget(pron_lbl, 2)

        heard_lbl = QLabel(f"{heard}×", self)
        heard_lbl.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 12px; color: {Colors.MUTE}; background: transparent;"
        )
        heard_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        heard_lbl.setFixedWidth(40)
        layout.addWidget(heard_lbl)

        conf_box = QWidget(self)
        conf_box.setStyleSheet("background: transparent;")
        conf_layout = QHBoxLayout(conf_box)
        conf_layout.setContentsMargins(0, 0, 0, 0)
        conf_layout.setSpacing(8)
        bar = _ConfidenceBar(confidence, self)
        conf_layout.addWidget(bar)
        pct_lbl = QLabel(f"{confidence}%", self)
        pct_lbl.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; background: transparent;"
        )
        pct_lbl.setFixedWidth(28)
        conf_layout.addWidget(pct_lbl)
        layout.addWidget(conf_box)

        del_btn = Btn(icon_name="trash", variant="ghost", size="sm", parent=self)
        del_btn.setToolTip("Delete")
        del_btn.clicked.connect(self.delete_clicked.emit)
        layout.addWidget(del_btn)


class _SwapRow(QWidget):
    delete_clicked = Signal()

    def __init__(self, from_text: str, to_text: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(14)

        from_lbl = QLabel(f'"{from_text}"', self)
        from_lbl.setWordWrap(True)
        from_lbl.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 13px; color: {Colors.INK_2}; background: transparent;"
        )
        layout.addWidget(from_lbl, 1)

        arrow = icon_label("arrow", 14, Colors.MUTE)
        layout.addWidget(arrow)

        to_lbl = QLabel(to_text, self)
        to_lbl.setWordWrap(True)
        to_lbl.setStyleSheet(
            f"font-size: 13px; color: {Colors.INK}; font-weight: 500; background: transparent;"
        )
        layout.addWidget(to_lbl, 1)

        del_btn = Btn(icon_name="trash", variant="ghost", size="sm", parent=self)
        del_btn.clicked.connect(self.delete_clicked.emit)
        layout.addWidget(del_btn)


class _NicknameRow(QWidget):
    delete_clicked = Signal()

    def __init__(self, spoken: str, full_name: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {Colors.PAPER_3}; border: 1px solid {Colors.RULE}; border-radius: 9px;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(14)

        from_lbl = QLabel(f'"{spoken}"', self)
        from_lbl.setWordWrap(True)
        from_lbl.setStyleSheet(
            f"font-size: 13.5px; color: {Colors.INK_2}; background: transparent; border: none;"
        )
        layout.addWidget(from_lbl, 1)

        arrow = icon_label("arrow", 14, Colors.MUTE)
        layout.addWidget(arrow)

        to_lbl = QLabel(full_name, self)
        to_lbl.setWordWrap(True)
        to_lbl.setStyleSheet(
            f"font-size: 13.5px; color: {Colors.INK}; font-weight: 500; background: transparent; border: none;"
        )
        layout.addWidget(to_lbl, 1)

        del_btn = Btn(icon_name="trash", variant="ghost", size="sm", parent=self)
        del_btn.clicked.connect(self.delete_clicked.emit)
        layout.addWidget(del_btn)


class DictionaryPage(QWidget):
    word_added = Signal()
    word_deleted = Signal(int)
    replacement_added = Signal()
    replacement_deleted = Signal(int)
    nickname_added = Signal()
    nickname_deleted = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_tab = "vocab"

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(28, 28, 28, 28)
        self._layout.setSpacing(0)

        add_btn = Btn("Add entry", variant="primary", size="sm", icon_name="plus")
        add_btn.clicked.connect(self._on_add_clicked)
        header = SectionTitle(
            "Dictionary",
            "Teach NickWhispr the words it keeps getting wrong, and the swaps you make every time.",
            action_widget=add_btn,
        )
        self._layout.addWidget(header)

        tab_frame = QFrame(self)
        tab_frame.setStyleSheet(
            f"QFrame {{ background: {Colors.PAPER_2}; border: 1px solid {Colors.RULE}; "
            f"border-radius: 10px; padding: 4px; }}"
        )
        tab_layout = QHBoxLayout(tab_frame)
        tab_layout.setContentsMargins(4, 4, 4, 4)
        tab_layout.setSpacing(4)

        self._tab_vocab = _TabButton("Custom words (0)", active=True)
        self._tab_swap = _TabButton("Replacements (0)")
        self._tab_nick = _TabButton("Nicknames (0)")

        self._tab_vocab.clicked.connect(lambda: self._switch_tab("vocab"))
        self._tab_swap.clicked.connect(lambda: self._switch_tab("swap"))
        self._tab_nick.clicked.connect(lambda: self._switch_tab("nicknames"))

        tab_layout.addWidget(self._tab_vocab)
        tab_layout.addWidget(self._tab_swap)
        tab_layout.addWidget(self._tab_nick)
        tab_layout.addStretch()

        self._layout.addWidget(tab_frame)
        self._layout.addSpacing(16)

        self._content_area = QVBoxLayout()
        self._content_area.setContentsMargins(0, 0, 0, 0)
        self._content_area.setSpacing(0)
        self._layout.addLayout(self._content_area)
        self._layout.addStretch()

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._words: list[dict] = []
        self._replacements: list[dict] = []
        self._nicknames: list[dict] = []

    def _on_add_clicked(self):
        if self._current_tab == "vocab":
            self.word_added.emit()
        elif self._current_tab == "swap":
            self.replacement_added.emit()
        else:
            self.nickname_added.emit()

    def _switch_tab(self, tab: str):
        self._current_tab = tab
        self._tab_vocab.set_active(tab == "vocab")
        self._tab_swap.set_active(tab == "swap")
        self._tab_nick.set_active(tab == "nicknames")
        self._rebuild_content()

    def _clear_content(self):
        while self._content_area.count():
            item = self._content_area.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _rebuild_content(self):
        self._clear_content()
        if self._current_tab == "vocab":
            self._build_vocab()
        elif self._current_tab == "swap":
            self._build_swap()
        else:
            self._build_nicknames()

    def _build_vocab(self):
        card = Card(padded=False)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet("background: transparent;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(18, 12, 18, 12)
        h_layout.setSpacing(12)

        for text, stretch in [("WORD", 3), ("PRONUNCIATION HINT", 2)]:
            lbl = QLabel(text, self)
            lbl.setStyleSheet(
                f"font-size: 11px; color: {Colors.MUTE}; letter-spacing: 0.8px; background: transparent;"
            )
            h_layout.addWidget(lbl, stretch)
        for text, w in [("HEARD", 40), ("CONFIDENCE", 100)]:
            lbl = QLabel(text, self)
            lbl.setStyleSheet(
                f"font-size: 11px; color: {Colors.MUTE}; letter-spacing: 0.8px; background: transparent;"
            )
            lbl.setFixedWidth(w)
            if text == "HEARD":
                lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            h_layout.addWidget(lbl)
        spacer_lbl = QLabel("", self)
        spacer_lbl.setFixedWidth(72)
        spacer_lbl.setStyleSheet("background: transparent;")
        h_layout.addWidget(spacer_lbl)
        card_layout.addWidget(header)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {Colors.RULE};")
        card_layout.addWidget(sep)

        for i, w in enumerate(self._words):
            row = _VocabRow(w["word"], w.get("pronunciation", ""), w.get("heard", 0), w.get("confidence", 0))
            idx = i
            row.delete_clicked.connect(lambda idx=idx: self.word_deleted.emit(idx))
            card_layout.addWidget(row)
            if i < len(self._words) - 1:
                line = QFrame()
                line.setFixedHeight(1)
                line.setStyleSheet(f"background: {Colors.RULE_2};")
                card_layout.addWidget(line)

        self._content_area.addWidget(card)

    def _build_swap(self):
        card = Card(padded=False)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet("background: transparent;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(18, 12, 18, 12)
        h_layout.setSpacing(14)
        for text in ["WHEN I SAY…", "", "TYPE…", ""]:
            lbl = QLabel(text, self)
            lbl.setStyleSheet(
                f"font-size: 11px; color: {Colors.MUTE}; letter-spacing: 0.8px; background: transparent;"
            )
            if text:
                h_layout.addWidget(lbl, 1)
            else:
                lbl.setFixedWidth(30)
                h_layout.addWidget(lbl)
        card_layout.addWidget(header)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {Colors.RULE};")
        card_layout.addWidget(sep)

        for i, s in enumerate(self._replacements):
            row = _SwapRow(s["from"], s["to"])
            idx = i
            row.delete_clicked.connect(lambda idx=idx: self.replacement_deleted.emit(idx))
            card_layout.addWidget(row)
            if i < len(self._replacements) - 1:
                line = QFrame()
                line.setFixedHeight(1)
                line.setStyleSheet(f"background: {Colors.RULE_2};")
                card_layout.addWidget(line)

        self._content_area.addWidget(card)

    def _build_nicknames(self):
        card = Card(padded=True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(8)

        desc = QLabel(
            "Tell Qwen who's who so it gets the right name in context. Useful for replies.",
            self,
        )
        desc.setStyleSheet(
            f"font-size: 13.5px; color: {Colors.INK_2}; background: transparent; border: none;"
        )
        desc.setWordWrap(True)
        card_layout.addWidget(desc)
        card_layout.addSpacing(6)

        for i, n in enumerate(self._nicknames):
            row = _NicknameRow(n["spoken"], n["full_name"])
            idx = i
            row.delete_clicked.connect(lambda idx=idx: self.nickname_deleted.emit(idx))
            card_layout.addWidget(row)

        self._content_area.addWidget(card)

    def set_words(self, words: list[dict]):
        self._words = words
        self._tab_vocab.setText(f"Custom words ({len(words)})")
        if self._current_tab == "vocab":
            self._rebuild_content()

    def set_replacements(self, replacements: list[dict]):
        self._replacements = replacements
        self._tab_swap.setText(f"Replacements ({len(replacements)})")
        if self._current_tab == "swap":
            self._rebuild_content()

    def set_nicknames(self, nicknames: list[dict]):
        self._nicknames = nicknames
        self._tab_nick.setText(f"Nicknames ({len(nicknames)})")
        if self._current_tab == "nicknames":
            self._rebuild_content()
