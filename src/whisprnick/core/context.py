"""Destination-app awareness: what kind of text box are we pasting into?

Wispr Flow uses the frontmost app to pick tone (email vs chat vs code). We
do the same from the foreground process name and window title.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppContext:
    kind: str          # email | chat | code | notes | document | generic
    label: str         # human-readable, shown in the HUD / prompt
    guidance: str      # one sentence for the cleanup model


_EMAIL_APPS = {"outlook", "mail", "thunderbird", "hey", "spark", "superhuman"}
_CHAT_APPS = {"slack", "teams", "discord", "whatsapp", "telegram", "signal", "messenger", "messages"}
_CODE_APPS = {"vs code", "code", "terminal", "windowsterminal", "cursor", "pycharm", "idea", "webstorm",
              "sublime_text", "notepad++", "powershell", "cmd", "conhost", "alacritty", "wezterm"}
_NOTES_APPS = {"notion", "obsidian", "onenote", "notepad", "evernote", "logseq", "bear", "apple notes"}
_DOC_APPS = {"word", "winword", "docs", "pages", "libreoffice", "excel", "powerpoint", "powerpnt"}

_TITLE_HINTS = [
    ("gmail", "email"), ("outlook", "email"), ("mail -", "email"), ("compose", "email"),
    ("slack", "chat"), ("teams", "chat"), ("discord", "chat"), ("whatsapp", "chat"),
    ("messenger", "chat"), ("telegram", "chat"),
    ("google docs", "document"), ("- word", "document"), ("notion", "notes"),
    ("github", "code"), ("gitlab", "code"), ("jira", "notes"), ("linear", "notes"),
    ("chatgpt", "chat"), ("claude", "chat"), ("gemini", "chat"),
]

_GUIDANCE = {
    "email": "The text is going into an email. Use complete sentences and proper paragraphs. "
             "Do not invent a greeting, subject line or sign-off.",
    "chat": "The text is going into a chat message. Keep it conversational and concise; "
            "a single short paragraph is usually right. Do not make it formal. "
            "If the whole message is one short sentence, leave off the final full stop.",
    "code": "The text is going into a code editor or terminal. Keep it plain and literal, "
            "one paragraph, no markdown, no bullet points, no smart quotes.",
    "notes": "The text is going into a notes app. Keep the speaker's structure; "
             "bullet points are fine if they clearly listed items.",
    "document": "The text is going into a document. Use complete sentences and paragraphs.",
    "generic": "Keep the speaker's structure and register.",
}


def detect_app_context(app_name: str, window_title: str = "") -> AppContext:
    name = (app_name or "").strip().lower()
    title = (window_title or "").strip().lower()

    kind = "generic"
    if name in _EMAIL_APPS:
        kind = "email"
    elif name in _CHAT_APPS:
        kind = "chat"
    elif name in _CODE_APPS:
        kind = "code"
    elif name in _NOTES_APPS:
        kind = "notes"
    elif name in _DOC_APPS:
        kind = "document"
    else:
        for needle, k in _TITLE_HINTS:
            if needle in title:
                kind = k
                break

    label = app_name or (window_title[:40] if window_title else "active window")
    return AppContext(kind=kind, label=label, guidance=_GUIDANCE[kind])
