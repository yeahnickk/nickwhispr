"""Text normalisation shared by the cleanup step and the clipboard injector.

Everything here is pure string work so it can be unit-tested without Qt,
Whisper or Ollama.
"""

from __future__ import annotations

import re

# Typographic characters that LLMs and Whisper love to emit but that look
# wrong (or break things) once pasted into a terminal, code editor or form.
_CHAR_MAP = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "–": "-",          # en dash
    "—": " - ",        # em dash
    "―": " - ",        # horizontal bar
    "−": "-",          # minus sign
    "…": "...",        # ellipsis
    " ": " ",          # non-breaking space
    " ": " ",          # narrow no-break space
    " ": " ",          # thin space
    "​": "",           # zero-width space
    "‌": "", "‍": "", "﻿": "",
}

_LLM_PREFIXES = re.compile(
    r"^\s*(?:here(?:'s| is) (?:the |your )?(?:cleaned(?:[- ]up)? |corrected |edited )?"
    r"(?:transcript|text|version)\s*:?|cleaned(?:[- ]up)? (?:transcript|text|version)\s*:|"
    r"output\s*:|transcript\s*:|corrected text\s*:)\s*",
    re.IGNORECASE,
)

_FENCE = re.compile(r"^\s*```[a-zA-Z]*\s*\n(.*?)\n\s*```\s*$", re.DOTALL)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_TRANSCRIPT_TAG = re.compile(r"</?transcript>", re.IGNORECASE)


def normalize_chars(text: str) -> str:
    """Replace smart quotes, dashes and odd whitespace with plain ASCII."""
    for src, dst in _CHAR_MAP.items():
        if src in text:
            text = text.replace(src, dst)
    return text


def tidy_text(text: str) -> str:
    """Whitespace and punctuation hygiene for text about to be pasted.

    - normalises line endings
    - strips trailing spaces on every line
    - collapses runs of spaces and 3+ blank lines
    - removes stray spaces before , . ! ? ; : and after ( [
    - fixes doubled punctuation like ",," or " .."
    """
    if not text:
        return ""
    text = normalize_chars(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +\n", "\n", text)
    text = re.sub(r"\n +", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # "word ," -> "word,"  but leave "..." alone
    text = re.sub(r"(?<=\S) +([,;:!?])", r"\1", text)
    text = re.sub(r"(?<=\w) +\.(?!\.)", ".", text)
    text = re.sub(r"([(\[]) +", r"\1", text)
    text = re.sub(r" +([)\]])", r"\1", text)
    text = re.sub(r",{2,}", ",", text)
    text = re.sub(r"(?<!\.)\.\.(?!\.)", ".", text)
    return text.strip()


def strip_llm_wrapping(raw: str) -> str:
    """Remove the scaffolding a small model tends to add around its answer."""
    if not raw:
        return ""
    text = _THINK.sub("", raw)
    text = _TRANSCRIPT_TAG.sub("", text).strip()
    m = _FENCE.match(text)
    if m:
        text = m.group(1).strip()
    text = _LLM_PREFIXES.sub("", text, count=1).strip()
    # Only unwrap quotes when the whole reply is quoted; never eat a
    # legitimate closing quote at the end of a sentence.
    for q in ('"', "'", "“", "‘"):
        closing = {"“": "”", "‘": "’"}.get(q, q)
        if len(text) >= 2 and text.startswith(q) and text.endswith(closing):
            inner = text[1:-1]
            if q not in inner and closing not in inner:
                text = inner.strip()
            break
    return text


def _match_case(source: str, replacement: str) -> str:
    """Keep sentence-initial capitalisation when swapping 'btw' -> 'by the way'."""
    if source[:1].isupper() and replacement[:1].islower():
        return replacement[0].upper() + replacement[1:]
    return replacement


def apply_replacements(text: str, mapping: dict[str, str]) -> str:
    """Case-insensitive, whole-word replacement. Longest triggers win."""
    if not text or not mapping:
        return text
    for trigger in sorted(mapping, key=len, reverse=True):
        trigger = trigger.strip()
        if not trigger:
            continue
        pattern = re.compile(
            r"(?<![\w])" + re.escape(trigger) + r"(?![\w])",
            re.IGNORECASE,
        )
        replacement = mapping[trigger]
        text = pattern.sub(lambda m: _match_case(m.group(0), replacement), text)
    return text


# Pure disfluencies: safe to delete without a model. Words like "like",
# "so" and "right" are deliberately NOT here; only the LLM has enough
# context to know whether they carry meaning.
_FILLER_ONLY = re.compile(
    r"(?<![\w'])(?:um+|uh+|uhm|erm|hmm+|mm+|ah+|er+|you know|i mean)(?![\w'])[,.]?\s*",
    re.IGNORECASE,
)
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "at", "for",
    "is", "are", "was", "were", "be", "been", "it", "that", "this", "with",
    "as", "by", "from", "so", "if", "we", "i", "you", "he", "she", "they",
    "them", "our", "your", "my", "me", "us", "do", "did", "does", "have",
    "has", "had", "not", "no", "yes", "just", "about", "into", "up", "out",
    "then", "than", "there", "here", "what", "which", "who", "when", "where",
    "how", "will", "would", "can", "could", "should", "also", "some", "any",
}


def content_words(text: str) -> list[str]:
    """Lower-cased alphabetic tokens minus stopwords, for overlap checks."""
    return [w for w in re.findall(r"[a-z0-9']+", text.lower())
            if len(w) > 2 and w not in _STOPWORDS]


def light_clean(text: str) -> str:
    """Deterministic fallback when the model's answer is rejected: drop
    pure fillers, fix sentence capitals, make sure it ends with punctuation."""
    if not text:
        return ""
    text = _FILLER_ONLY.sub("", text)
    text = tidy_text(text)
    if not text:
        return ""
    # Capitalise sentence starts.
    text = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)
    if text[-1] not in ".!?\"')":
        text += "."
    return text


_SPOKEN_COMMANDS = [
    (re.compile(r"[,.;:]?\s*\bnew paragraph\b[,.;:]?\s*", re.IGNORECASE), "\n\n"),
    (re.compile(r"[,.;:]?\s*\bnew line\b[,.;:]?\s*", re.IGNORECASE), "\n"),
]


def apply_spoken_commands(text: str) -> str:
    """Turn spoken 'new paragraph' / 'new line' into real breaks, close the
    line before the break with a full stop, and capitalise what follows."""
    if not text:
        return text

    def _break(replacement):
        def _sub(m):
            before = m.string[:m.start()].rstrip()
            needs_stop = bool(before) and before[-1] not in ".!?:;\"')"
            return ("." if needs_stop else "") + replacement
        return _sub

    for pattern, replacement in _SPOKEN_COMMANDS:
        text = pattern.sub(_break(replacement), text)
    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln[:1].upper() + ln[1:] if ln else ln for ln in lines]
    return "\n".join(lines).strip()


# Explicit self-correction triggers. Restating without a trigger is left to
# the model; these are unambiguous enough to handle deterministically.
_BACKTRACK_TRIGGER = r"(?:no,?\s+wait,?\s*)?(?:scratch|strike|forget) that"
# Trigger with nothing after it: the correction was already applied, so
# only the trigger itself goes.
_BACKTRACK_TAIL = re.compile(
    r"[,\s]*" + _BACKTRACK_TRIGGER + r"[.!?,]?\s*$", re.IGNORECASE
)
# Trigger followed by more speech: drop the clause/sentence before it.
_BACKTRACK_MID = re.compile(
    r"([^.!?\n]*[.!?,]?\s*)" + _BACKTRACK_TRIGGER + r"[,.]?\s*(?=\S)", re.IGNORECASE
)


def apply_backtrack(text: str) -> str:
    """Remove 'scratch that' style corrections that survived cleanup.

    'Let's meet at 3, no wait, scratch that, let's meet at 4.' -> 'Let's meet at 4.'
    'Send it to Bob. Scratch that, send it to Alice.'          -> 'Send it to Alice.'
    A trigger with nothing after it just gets deleted.
    """
    if not text or not re.search(r"(scratch|strike|forget) that", text, re.IGNORECASE):
        return text
    text = _BACKTRACK_TAIL.sub("", text)
    text = _BACKTRACK_MID.sub("", text)
    text = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)
    return tidy_text(text)


def for_clipboard(text: str) -> str:
    """Final form for CF_UNICODETEXT: tidy, ASCII punctuation, CRLF line ends."""
    text = tidy_text(text)
    return text.replace("\n", "\r\n")
