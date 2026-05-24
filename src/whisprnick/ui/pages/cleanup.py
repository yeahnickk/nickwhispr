from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QScrollArea, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from whisprnick.ui.widgets.card import Card
from whisprnick.ui.widgets.btn import Btn
from whisprnick.ui.widgets.pill import Pill
from whisprnick.ui.widgets.toggle import Toggle
from whisprnick.ui.widgets.field_label import FieldLabel
from whisprnick.ui.widgets.section_title import SectionTitle
from whisprnick.ui.styles.theme import Colors, Fonts
from whisprnick.core.cleanup import CleanupEngine, DEFAULT_TEMPLATE


_BEHAVIORS = [
    ("fillers", "Trim filler words", "um, uh, like, you know, kind of", True),
    ("grammar", "Fix grammar", "subject-verb agreement, tense", True),
    ("punctuation", "Add punctuation", "periods, commas, quotes", True),
    ("capitalize", "Capitalize properly", "sentences and proper nouns", True),
    ("paragraphs", "Insert paragraph breaks", "when topic shifts", True),
    ("formal", "Bump formality", "for emails to people who matter", False),
    ("bullets", "Detect list intent", "convert spoken lists to bullets", False),
    ("profanity", "Censor profanity", "f*** it", False),
]

_RAW_PREVIEW = (
    "so um like the meeting on tuesday went pretty well I think we should "
    "you know follow up with marcus tomorrow morning about the budget thing "
    "and also remind him about the q3 roadmap"
)

_CLEAN_PREVIEW = (
    "The meeting on Tuesday went pretty well. I think we should follow up "
    "with Marcus tomorrow morning about the budget thing, and also remind "
    "him about the Q3 roadmap."
)


def _build_preview_prompt(behaviors: dict, template: str = "") -> str:
    rules = dict(behaviors)
    return CleanupEngine.build_system_prompt(rules, template=template)


class _BehaviorRow(QWidget):
    toggled = Signal(str, bool)

    def __init__(self, key: str, label: str, description: str, default: bool, parent=None):
        super().__init__(parent)
        self._key = key
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(12)

        text_area = QVBoxLayout()
        text_area.setSpacing(2)

        lbl = QLabel(label, self)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"font-size: 13.5px; color: {Colors.INK}; font-weight: 500; background: transparent;"
        )
        text_area.addWidget(lbl)

        sub = QLabel(description, self)
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"font-size: 12px; color: {Colors.MUTE}; background: transparent;"
        )
        text_area.addWidget(sub)

        layout.addLayout(text_area, 1)

        self._toggle = Toggle(on=default, size="md")
        self._toggle.toggled_signal.connect(lambda v: self.toggled.emit(self._key, v))
        layout.addWidget(self._toggle)

    @property
    def is_on(self) -> bool:
        return self._toggle.is_on

    @is_on.setter
    def is_on(self, value: bool):
        self._toggle.is_on = value


class CleanupPage(QWidget):
    profile_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_preset = "default"
        self._behavior_rows: dict[str, _BehaviorRow] = {}

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
            "Cleanup rules",
            "Toggles below get baked into the prompt sent to the local cleanup model. Preview live on the right.",
        )
        main_layout.addWidget(header)

        columns = QHBoxLayout()
        columns.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(0)

        self._current_preset = "default"

        left.addSpacing(24)
        behav_label = FieldLabel("Behaviors")
        left.addWidget(behav_label)
        left.addSpacing(12)

        for key, label, desc, default in _BEHAVIORS:
            row = _BehaviorRow(key, label, desc, default)
            row.toggled.connect(self._on_behavior_toggled)
            self._behavior_rows[key] = row
            left.addWidget(row)

            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background: {Colors.RULE_2};")
            left.addWidget(sep)

        left.addSpacing(22)

        tmpl_header = QHBoxLayout()
        tmpl_label = FieldLabel("Prompt template")
        tmpl_header.addWidget(tmpl_label)
        tmpl_header.addStretch()
        reset_btn = Btn("Reset to default", variant="ghost", size="sm")
        reset_btn.clicked.connect(self._on_reset_template)
        tmpl_header.addWidget(reset_btn)
        left.addLayout(tmpl_header)
        left.addSpacing(8)

        self._template_edit = QTextEdit()
        self._template_edit.setPlainText(DEFAULT_TEMPLATE)
        self._template_edit.setMinimumHeight(200)
        self._template_edit.setMaximumHeight(400)
        self._template_edit.setStyleSheet(
            f"QTextEdit {{ font-family: \"{Fonts.MONO}\"; font-size: 12.5px; "
            f"border: 1px solid {Colors.RULE}; border-radius: 10px; "
            f"background: {Colors.PAPER_3}; color: {Colors.INK_2}; "
            f"padding: 12px; }}"
        )
        self._template_edit.textChanged.connect(self._emit_profile)
        left.addWidget(self._template_edit)

        hint = QLabel("Placeholders:  {{RULES}}   {{VOCABULARY}}   {{REPLACEMENTS}}", self)
        hint.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; "
            f"background: transparent; padding-top: 4px;"
        )
        left.addWidget(hint)
        left.addStretch()

        left_widget = QWidget()
        left_widget.setStyleSheet("background: transparent;")
        left_widget.setLayout(left)

        right = QVBoxLayout()
        right.setSpacing(14)

        preview_card = Card(padded=False)
        preview_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        preview_header = QWidget()
        preview_header.setStyleSheet("background: transparent;")
        ph_layout = QHBoxLayout(preview_header)
        ph_layout.setContentsMargins(16, 12, 16, 12)
        lp_label = FieldLabel("Live preview")
        ph_layout.addWidget(lp_label)
        ph_layout.addStretch()
        from whisprnick.config import OLLAMA_MODEL
        model_pill = Pill(f"{OLLAMA_MODEL}", tone="accent", icon_name="sparkle")
        ph_layout.addWidget(model_pill)
        preview_layout.addWidget(preview_header)

        sep1 = QFrame()
        sep1.setFixedHeight(1)
        sep1.setStyleSheet(f"background: {Colors.RULE};")
        preview_layout.addWidget(sep1)

        raw_section = QWidget()
        raw_section.setStyleSheet("background: transparent;")
        raw_lay = QVBoxLayout(raw_section)
        raw_lay.setContentsMargins(16, 16, 16, 16)
        raw_lay.setSpacing(6)
        raw_tag = QLabel("RAW", self)
        raw_tag.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; background: transparent;"
        )
        raw_lay.addWidget(raw_tag)
        self._raw_text = QLabel(_RAW_PREVIEW, self)
        self._raw_text.setWordWrap(True)
        self._raw_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._raw_text.setStyleSheet(
            f"font-size: 13.5px; line-height: 155%; color: {Colors.MUTE}; background: transparent;"
        )
        raw_lay.addWidget(self._raw_text)
        preview_layout.addWidget(raw_section)

        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background: {Colors.RULE_2};")
        preview_layout.addWidget(sep2)

        clean_section = QWidget()
        clean_section.setStyleSheet("background: transparent;")
        clean_lay = QVBoxLayout(clean_section)
        clean_lay.setContentsMargins(16, 16, 16, 16)
        clean_lay.setSpacing(6)
        clean_tag = QLabel("CLEANED", self)
        clean_tag.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.ACCENT_2}; background: transparent;"
        )
        clean_lay.addWidget(clean_tag)
        self._clean_text = QLabel(_CLEAN_PREVIEW, self)
        self._clean_text.setWordWrap(True)
        self._clean_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._clean_text.setStyleSheet(
            f"font-size: 13.5px; line-height: 155%; color: {Colors.INK}; background: transparent;"
        )
        clean_lay.addWidget(self._clean_text)
        preview_layout.addWidget(clean_section)

        right.addWidget(preview_card)

        prompt_card = Card(padded=True)
        prompt_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        prompt_card.setStyleSheet(
            f"Card {{ background: {Colors.PAPER_2}; border: 1px solid {Colors.RULE}; "
            f"border-radius: 14px; padding: 18px; }}"
        )
        prompt_layout = QVBoxLayout(prompt_card)
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        prompt_layout.setSpacing(10)
        prompt_title = FieldLabel("Compiled system prompt")
        prompt_layout.addWidget(prompt_title)
        initial_prompt = _build_preview_prompt(
            {key: default for key, _, _, default in _BEHAVIORS},
        )
        self._prompt_label = QLabel(initial_prompt, self)
        self._prompt_label.setWordWrap(True)
        self._prompt_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._prompt_label.setTextFormat(Qt.TextFormat.PlainText)
        self._prompt_label.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11.5px; color: {Colors.INK_2}; "
            f"line-height: 165%; background: transparent;"
        )
        prompt_layout.addWidget(self._prompt_label)
        right.addWidget(prompt_card)
        right.addStretch()

        right_widget = QWidget()
        right_widget.setStyleSheet("background: transparent;")
        right_widget.setLayout(right)
        right_widget.setMinimumWidth(280)
        right_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        columns.addWidget(left_widget, 1)
        columns.addWidget(right_widget, 1)
        main_layout.addLayout(columns)

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._emit_profile()

    def _on_behavior_toggled(self, key: str, value: bool):
        self._emit_profile()

    def _on_reset_template(self):
        self._template_edit.setPlainText(DEFAULT_TEMPLATE)

    def _emit_profile(self):
        profile = self.get_profile()
        self.profile_changed.emit(profile)
        compiled = _build_preview_prompt(profile["behaviors"], template=profile["template"])
        self._prompt_label.setText(compiled)

    def set_profile(self, profile):
        for key, row in self._behavior_rows.items():
            val = getattr(profile, key, None)
            if val is not None:
                row.is_on = val
        template = getattr(profile, "prompt_template", "") or ""
        if template:
            self._template_edit.setPlainText(template)
        else:
            self._template_edit.setPlainText(DEFAULT_TEMPLATE)

    def get_profile(self) -> dict:
        behaviors = {key: row.is_on for key, row in self._behavior_rows.items()}
        return {
            "preset": self._current_preset,
            "behaviors": behaviors,
            "template": self._template_edit.toPlainText(),
        }
