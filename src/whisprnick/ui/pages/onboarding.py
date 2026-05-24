from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QFrame, QSizePolicy, QStackedWidget, QPushButton,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor

from whisprnick.ui.widgets.card import Card
from whisprnick.ui.widgets.btn import Btn
from whisprnick.ui.widgets.kbd import Kbd
from whisprnick.ui.widgets.pipeline import PipelineWidget
from whisprnick.ui.widgets.mic_orb import MicOrb
from whisprnick.ui.widgets.icons import icon_label
from whisprnick.ui.styles.theme import Colors, Fonts


class _ProgressDots(QWidget):
    def __init__(self, total: int = 6, parent=None):
        super().__init__(parent)
        self._total = total
        self._current = 0
        self.setFixedHeight(3)
        self.setStyleSheet("background: transparent;")

    def set_current(self, step: int):
        self._current = step
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        dot_w = 28
        gap = 4
        total_w = self._total * dot_w + (self._total - 1) * gap
        start_x = (self.width() - total_w) / 2
        for i in range(self._total):
            x = start_x + i * (dot_w + gap)
            color = QColor(Colors.INK) if i <= self._current else QColor(Colors.RULE)
            p.setBrush(color)
            p.drawRoundedRect(int(x), 0, dot_w, 3, 1.5, 1.5)
        p.end()


class _HotkeyOption(QPushButton):
    def __init__(self, key: str, recommended: bool = False, parent=None):
        super().__init__(parent)
        self._key = key
        self._selected = recommended
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()
        self.setMinimumHeight(60)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._kbd = Kbd(key)
        if self._selected:
            self._kbd.setStyleSheet(
                f"Kbd {{ min-width: 22px; height: 22px; padding: 0px 6px; "
                f"border: 1px solid rgba(255,255,255,0.2); border-bottom: 2px solid rgba(255,255,255,0.2); "
                f"border-radius: 6px; background: rgba(255,255,255,0.1); font-size: 11px; "
                f"font-family: \"{Fonts.MONO}\"; color: {Colors.PAPER}; }}"
            )
        layout.addWidget(self._kbd, 0, Qt.AlignmentFlag.AlignCenter)

        if recommended:
            rec_lbl = QLabel("Recommended", self)
            rec_lbl.setStyleSheet(
                f"font-size: 11px; color: rgba(255,255,255,0.7); background: transparent; border: none;"
            )
            rec_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(rec_lbl)

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_style()
        if selected:
            self._kbd.setStyleSheet(
                f"Kbd {{ min-width: 22px; height: 22px; padding: 0px 6px; "
                f"border: 1px solid rgba(255,255,255,0.2); border-bottom: 2px solid rgba(255,255,255,0.2); "
                f"border-radius: 6px; background: rgba(255,255,255,0.1); font-size: 11px; "
                f"font-family: \"{Fonts.MONO}\"; color: {Colors.PAPER}; }}"
            )
        else:
            self._kbd.setStyleSheet(
                f"Kbd {{ min-width: 22px; height: 22px; padding: 0px 6px; "
                f"border: 1px solid {Colors.RULE}; border-bottom: 2px solid {Colors.RULE}; "
                f"border-radius: 6px; background: {Colors.PAPER_3}; font-size: 11px; "
                f"font-family: \"{Fonts.MONO}\"; color: {Colors.INK_2}; }}"
            )

    def _apply_style(self):
        if self._selected:
            self.setStyleSheet(
                f"_HotkeyOption {{ padding: 16px; background: {Colors.INK}; color: {Colors.PAPER}; "
                f"border: 1px solid {Colors.INK}; border-radius: 10px; font-size: 13px; "
                f"font-weight: 500; }}"
            )
        else:
            self.setStyleSheet(
                f"_HotkeyOption {{ padding: 16px; background: {Colors.PAPER_3}; color: {Colors.INK}; "
                f"border: 1px solid {Colors.RULE}; border-radius: 10px; font-size: 13px; "
                f"font-weight: 500; }}"
                f"_HotkeyOption:hover {{ background: {Colors.PAPER_2}; }}"
            )


class _StatCard(QWidget):
    def __init__(self, value: str, label: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {Colors.PAPER_2}; border: 1px solid {Colors.RULE}; border-radius: 10px;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        val_lbl = QLabel(value, self)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_lbl.setStyleSheet(
            f"font-family: \"{Fonts.SERIF}\"; font-size: 28px; color: {Colors.INK}; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(val_lbl)

        desc_lbl = QLabel(label, self)
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setStyleSheet(
            f"font-size: 12px; color: {Colors.MUTE}; background: transparent; border: none;"
        )
        layout.addWidget(desc_lbl)


_STEPS = [
    {
        "title": "Hi, I'm NickWhispr.",
        "sub": "You talk. I type. With one warm cup of Qwen on the side.",
        "next": "Let's set it up",
    },
    {
        "title": "How it works",
        "sub": "Two steps. Whisper transcribes, Qwen cleans up — both run on your machine.",
        "next": "Got it",
    },
    {
        "title": "Pick your hotkey",
        "sub": "What button summons the mic?",
        "next": "Continue",
    },
    {
        "title": "Microphone permission",
        "sub": "Windows will ask. Say yes, otherwise I'm just a paperweight.",
        "next": "I allowed it",
    },
    {
        "title": "Try your first dictation",
        "sub": 'Hold R Alt and say: "hello world, this is my first test".',
        "next": "Looks good",
    },
    {
        "title": "All set.",
        "sub": "We've set sensible defaults: 60s max recording, 3s silence cutoff. Everything runs locally. Tweak any time in Safeguards.",
        "next": "Take me in →",
    },
]


class OnboardingPage(QWidget):
    completed = Signal()
    navigate_to = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._step = 0
        self._selected_hotkey = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        wrapper = QWidget(self)
        wrapper.setFixedWidth(520)
        wrapper.setStyleSheet("background: transparent;")
        self._wrapper_layout = QVBoxLayout(wrapper)
        self._wrapper_layout.setContentsMargins(0, 28, 0, 28)
        self._wrapper_layout.setSpacing(0)

        self._dots = _ProgressDots(len(_STEPS))
        self._wrapper_layout.addWidget(self._dots)
        self._wrapper_layout.addSpacing(28)

        self._title = QLabel("", self)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setWordWrap(True)
        self._title.setStyleSheet(
            f"font-family: \"{Fonts.SERIF}\"; font-size: 38px; color: {Colors.INK}; "
            f"letter-spacing: -0.5px; background: transparent;"
        )
        self._wrapper_layout.addWidget(self._title)
        self._wrapper_layout.addSpacing(10)

        self._subtitle = QLabel("", self)
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle.setWordWrap(True)
        self._subtitle.setStyleSheet(
            f"font-size: 14.5px; color: {Colors.MUTE}; line-height: 150%; background: transparent;"
        )
        self._wrapper_layout.addWidget(self._subtitle)
        self._wrapper_layout.addSpacing(28)

        self._body_stack = QStackedWidget()
        self._body_stack.setStyleSheet("background: transparent;")
        self._build_step_bodies()
        self._wrapper_layout.addWidget(self._body_stack)
        self._wrapper_layout.addSpacing(28)

        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)

        self._back_btn = Btn("Skip", variant="ghost", size="sm")
        self._back_btn.clicked.connect(self._on_back)
        nav_row.addWidget(self._back_btn)

        nav_row.addStretch()

        self._step_label = QLabel("1 / 6", self)
        self._step_label.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 11px; color: {Colors.MUTE}; background: transparent;"
        )
        nav_row.addWidget(self._step_label)

        nav_row.addStretch()

        self._next_btn = Btn("Let's set it up", variant="primary", size="md")
        self._next_btn.clicked.connect(self._on_next)
        nav_row.addWidget(self._next_btn)

        self._wrapper_layout.addLayout(nav_row)
        outer.addWidget(wrapper)

        self._update_step()

    def _build_step_bodies(self):
        # Step 0: Avatar
        avatar_page = QWidget()
        avatar_page.setStyleSheet("background: transparent;")
        av_lay = QHBoxLayout(avatar_page)
        av_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av_lay.setContentsMargins(0, 20, 0, 20)
        avatar = QLabel("N", self)
        avatar.setFixedSize(96, 96)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            f"background: {Colors.INK}; color: {Colors.PAPER}; border-radius: 48px; "
            f"font-family: \"{Fonts.SERIF}\"; font-size: 36px;"
        )
        av_lay.addWidget(avatar)
        self._body_stack.addWidget(avatar_page)

        # Step 1: Pipeline
        pipe_page = QWidget()
        pipe_page.setStyleSheet(
            f"background: {Colors.PAPER_2}; border: 1px solid {Colors.RULE}; border-radius: 12px;"
        )
        pp_lay = QVBoxLayout(pipe_page)
        pp_lay.setContentsMargins(18, 18, 18, 18)
        self._pipeline = PipelineWidget()
        pp_lay.addWidget(self._pipeline)
        self._body_stack.addWidget(pipe_page)

        # Step 2: Hotkey picker
        hotkey_page = QWidget()
        hotkey_page.setStyleSheet("background: transparent;")
        hk_grid = QGridLayout(hotkey_page)
        hk_grid.setSpacing(10)
        keys = ["R Alt", "F13", "Caps Lock", "Win + Space", "Ctrl + ;", "Custom..."]
        self._hotkey_buttons: list[_HotkeyOption] = []
        for i, k in enumerate(keys):
            btn = _HotkeyOption(k, recommended=(i == 0))
            btn.clicked.connect(lambda checked=False, idx=i: self._select_hotkey(idx))
            self._hotkey_buttons.append(btn)
            hk_grid.addWidget(btn, i // 3, i % 3)
        self._body_stack.addWidget(hotkey_page)

        # Step 3: Mic permission
        mic_page = QWidget()
        mic_page.setStyleSheet(
            f"background: {Colors.PAPER_2}; border: 1px solid {Colors.RULE}; border-radius: 12px;"
        )
        mp_lay = QVBoxLayout(mic_page)
        mp_lay.setContentsMargins(24, 24, 24, 24)
        mp_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mp_lay.setSpacing(14)

        mic_bg = QWidget(self)
        mic_bg.setFixedSize(64, 64)
        mic_bg.setStyleSheet(
            f"background: {Colors.ACCENT_SOFT}; border-radius: 32px; border: none;"
        )
        mic_icon = icon_label("mic", 28, Colors.ACCENT_2)
        mic_icon.setParent(mic_bg)
        mic_icon.move(18, 18)
        mp_lay.addWidget(mic_bg, 0, Qt.AlignmentFlag.AlignCenter)

        perm_text = QLabel("NickWhispr would like to access your microphone", self)
        perm_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        perm_text.setStyleSheet(
            f"font-size: 13px; color: {Colors.INK_2}; background: transparent; border: none;"
        )
        mp_lay.addWidget(perm_text)

        perm_btns = QHBoxLayout()
        perm_btns.setAlignment(Qt.AlignmentFlag.AlignCenter)
        perm_btns.setSpacing(8)
        not_now_btn = Btn("Not now", variant="outline", size="sm")
        allow_btn = Btn("Allow", variant="accent", size="sm")
        perm_btns.addWidget(not_now_btn)
        perm_btns.addWidget(allow_btn)
        mp_lay.addLayout(perm_btns)
        self._body_stack.addWidget(mic_page)

        # Step 4: First dictation
        dictation_page = QWidget()
        dictation_page.setStyleSheet(
            f"background: {Colors.PAPER_2}; border: 1px solid {Colors.RULE}; border-radius: 12px;"
        )
        dp_lay = QVBoxLayout(dictation_page)
        dp_lay.setContentsMargins(28, 28, 28, 28)
        dp_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dp_lay.setSpacing(16)

        self._mic_orb = MicOrb()
        self._mic_orb.set_state("listening")
        dp_lay.addWidget(self._mic_orb, 0, Qt.AlignmentFlag.AlignCenter)

        timer_lbl = QLabel("listening · 0:04", self)
        timer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timer_lbl.setStyleSheet(
            f"font-family: \"{Fonts.MONO}\"; font-size: 13px; color: {Colors.MUTE}; "
            f"background: transparent; border: none;"
        )
        dp_lay.addWidget(timer_lbl)
        self._body_stack.addWidget(dictation_page)

        # Step 5: All set
        done_page = QWidget()
        done_page.setStyleSheet("background: transparent;")
        done_grid = QHBoxLayout(done_page)
        done_grid.setSpacing(10)
        for val, lbl in [("1:00", "max length"), ("3s", "silence cutoff")]:
            done_grid.addWidget(_StatCard(val, lbl))
        self._body_stack.addWidget(done_page)

    def _select_hotkey(self, idx: int):
        self._selected_hotkey = idx
        for i, btn in enumerate(self._hotkey_buttons):
            btn.set_selected(i == idx)

    def _update_step(self):
        step = _STEPS[self._step]
        self._dots.set_current(self._step)
        self._title.setText(step["title"])
        self._subtitle.setText(step["sub"])
        self._next_btn.setText(step["next"])
        self._step_label.setText(f"{self._step + 1} / {len(_STEPS)}")
        self._body_stack.setCurrentIndex(self._step)

        if self._step > 0:
            self._back_btn.setText("← Back")
        else:
            self._back_btn.setText("Skip")

    def _on_back(self):
        if self._step > 0:
            self._step -= 1
            self._update_step()
        else:
            self.navigate_to.emit("home")

    def _on_next(self):
        if self._step < len(_STEPS) - 1:
            self._step += 1
            self._update_step()
        else:
            self.completed.emit()
            self.navigate_to.emit("home")
