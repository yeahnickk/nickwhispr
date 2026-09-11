from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QScrollArea, QFrame, QSizePolicy, QPushButton,
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer

from whisprnick.ui.widgets.card import Card
from whisprnick.ui.widgets.btn import Btn
from whisprnick.ui.widgets.pill import Pill
from whisprnick.ui.widgets.toggle import Toggle
from whisprnick.ui.widgets.field_label import FieldLabel
from whisprnick.ui.widgets.section_title import SectionTitle
from whisprnick.ui.styles.theme import Colors, Fonts
from whisprnick.core.cleanup import CleanupEngine, DEFAULT_TEMPLATE
from whisprnick.core.textutil import light_clean


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

# Presets are separate saved profiles: toggles, extra instructions and
# template each. "raw" skips the model entirely.
PRESETS = [
    ("default", "Default"),
    ("email", "Email"),
    ("chat", "Chat"),
    ("doc", "Documents"),
    ("code", "Code"),
    ("raw", "Raw - no AI"),
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


class _PreviewWorker(QThread):
    """Runs the real cleanup engine on the sample text so the preview is
    actually live rather than a canned string."""
    finished_with = Signal(bool, str, int)  # ok, text, latency_ms

    def __init__(self, behaviors: dict, template: str, parent=None):
        super().__init__(parent)
        self._behaviors = dict(behaviors)
        self._template = template

    def run(self):
        try:
            from whisprnick.config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS
            engine = CleanupEngine(OLLAMA_URL, OLLAMA_MODEL, timeout=OLLAMA_TIMEOUT_SECONDS)
            if not engine.is_available():
                self.finished_with.emit(False, "", 0)
                return
            text, ms = engine.clean(_RAW_PREVIEW, self._behaviors, template=self._template)
            self.finished_with.emit(True, text, ms)
        except Exception:
            self.finished_with.emit(False, "", 0)


class _PresetPill(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"_PresetPill {{ padding: 7px 14px; border: 1px solid {Colors.RULE}; border-radius: 999px; "
            f"background: {Colors.PAPER_3}; color: {Colors.INK_2}; font-size: 12.5px; font-family: \"{Fonts.BODY}\"; }}"
            f"_PresetPill:hover {{ background: {Colors.PAPER_2}; }}"
            f"_PresetPill:checked {{ background: {Colors.INK}; color: {Colors.PAPER}; border-color: {Colors.INK}; }}"
        )


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
    preset_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_preset = "default"
        self._behavior_rows: dict[str, _BehaviorRow] = {}

        # Debounce so typing in the template box doesn't fire a request per key.
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(700)
        self._preview_timer.timeout.connect(self._run_preview)
        self._preview_worker: _PreviewWorker | None = None
        self._preview_dirty = True
        self._loading = False

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

        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        preset_row.addWidget(FieldLabel("Preset"))
        preset_row.addSpacing(6)
        self._preset_pills: dict[str, _PresetPill] = {}
        for key, label in PRESETS:
            pill = _PresetPill(label)
            pill.setChecked(key == "default")
            pill.clicked.connect(lambda checked=False, k=key: self._on_preset_clicked(k))
            self._preset_pills[key] = pill
            preset_row.addWidget(pill)
        preset_row.addStretch()
        main_layout.addLayout(preset_row)

        self._raw_note = QLabel(
            "Raw mode: Whisper's transcript with pure fillers stripped and tidied. No AI rewrite, fastest, "
            "and nothing can be misread as an instruction.", self)
        self._raw_note.setWordWrap(True)
        self._raw_note.setStyleSheet(
            f"font-size: 12.5px; color: {Colors.INK_2}; background: {Colors.PAPER_3}; "
            f"border: 1px solid {Colors.RULE}; border-radius: 9px; padding: 10px 12px; margin-top: 12px;")
        self._raw_note.hide()
        main_layout.addWidget(self._raw_note)

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

        left.addWidget(FieldLabel("Extra instructions"))
        left.addSpacing(8)
        self._suffix_edit = QTextEdit()
        self._suffix_edit.setPlaceholderText("e.g. Keep my technical jargon. Never use em dashes. Don't expand acronyms.")
        self._suffix_edit.setFixedHeight(72)
        self._suffix_edit.setStyleSheet(
            f"QTextEdit {{ font-size: 13px; border: 1px solid {Colors.RULE}; border-radius: 10px; "
            f"background: {Colors.PAPER_3}; color: {Colors.INK}; padding: 10px; }}"
        )
        self._suffix_edit.textChanged.connect(self._emit_profile)
        left.addWidget(self._suffix_edit)
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
        hint.setWordWrap(True)
        hint.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        hint.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; "
            f"background: transparent; padding-top: 4px;"
        )
        left.addWidget(hint)
        left.addStretch()

        left_widget = QWidget()
        left_widget.setStyleSheet("background: transparent;")
        left_widget.setLayout(left)
        self._left_widget = left_widget

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
        self._clean_tag = QLabel("CLEANED", self)
        self._clean_tag.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.ACCENT_2}; background: transparent;"
        )
        clean_lay.addWidget(self._clean_tag)
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

    def _rules_for(self, profile: dict) -> dict:
        rules = dict(profile["behaviors"])
        rules["prompt_suffix"] = profile["suffix"]
        return rules

    def _emit_profile(self):
        if self._loading:
            return
        profile = self.get_profile()
        self.profile_changed.emit(profile)
        self._prompt_label.setText(_build_preview_prompt(self._rules_for(profile), template=profile["template"]))
        self._preview_dirty = True
        if self.isVisible():
            self._preview_timer.start()

    # -- Presets --------------------------------------------------------

    def _on_preset_clicked(self, key: str):
        if key == self._current_preset:
            self._preset_pills[key].setChecked(True)
            return
        self.preset_selected.emit(key)

    def _apply_raw_mode(self, raw: bool):
        self._left_widget.setEnabled(not raw)
        self._raw_note.setVisible(raw)

    # ── Live preview ───────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if self._preview_dirty:
            self._preview_timer.start()

    def _run_preview(self):
        if self._preview_worker is not None and self._preview_worker.isRunning():
            self._preview_timer.start()  # try again once the current one finishes
            return
        profile = self.get_profile()
        self._preview_dirty = False
        if self._current_preset == "raw":
            self._clean_text.setText(light_clean(_RAW_PREVIEW))
            self._clean_tag.setText("RAW · no model")
            return
        self._clean_tag.setText("CLEANING…")
        self._preview_worker = _PreviewWorker(self._rules_for(profile), profile["template"], self)
        self._preview_worker.finished_with.connect(self._on_preview_done)
        self._preview_worker.finished.connect(self._preview_worker.deleteLater)
        self._preview_worker.start()

    def _on_preview_done(self, ok: bool, text: str, ms: int):
        if ok and text:
            self._clean_text.setText(text)
            self._clean_tag.setText(f"CLEANED · {ms} ms")
        else:
            self._clean_text.setText(_CLEAN_PREVIEW)
            self._clean_tag.setText("SAMPLE · Ollama offline")

    def set_profile(self, profile):
        """Load a saved profile into the editor without re-saving it."""
        self._loading = True
        try:
            preset = getattr(profile, "preset", "default") or "default"
            self._current_preset = preset
            for key, pill in self._preset_pills.items():
                pill.setChecked(key == preset)
            for key, row in self._behavior_rows.items():
                val = getattr(profile, key, None)
                if val is not None:
                    row.is_on = val
            self._suffix_edit.setPlainText(getattr(profile, "prompt_suffix", "") or "")
            template = getattr(profile, "prompt_template", "") or ""
            self._template_edit.setPlainText(template if template else DEFAULT_TEMPLATE)
            self._apply_raw_mode(preset == "raw")
        finally:
            self._loading = False
        p = self.get_profile()
        self._prompt_label.setText(_build_preview_prompt(self._rules_for(p), template=p["template"]))
        self._preview_dirty = True
        if self.isVisible():
            self._preview_timer.start()

    def get_profile(self) -> dict:
        behaviors = {key: row.is_on for key, row in self._behavior_rows.items()}
        return {
            "preset": self._current_preset,
            "behaviors": behaviors,
            "suffix": self._suffix_edit.toPlainText().strip(),
            "template": self._template_edit.toPlainText(),
        }
