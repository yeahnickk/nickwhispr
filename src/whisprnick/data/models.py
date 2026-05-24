from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class DictationEntry:
    id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    source_app: str = ""
    original_text: str = ""
    cleaned_text: str = ""
    cleanup_level: str = "light"
    cleanup_preset: str = "default"
    duration_seconds: float = 0.0
    word_count: int = 0
    filler_count: int = 0
    fillers_found: str = ""
    latency_ms: int = 0
    cost: float = 0.0
    whisper_model: str = "small"
    cleanup_model: str = "qwen2.5:3b"


@dataclass
class DictionaryWord:
    id: Optional[int] = None
    word: str = ""
    pronunciation: str = ""
    heard_count: int = 0
    confidence: int = 0
    source: str = "manual"
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Replacement:
    id: Optional[int] = None
    trigger: str = ""
    replacement: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Nickname:
    id: Optional[int] = None
    spoken: str = ""
    full_name: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CleanupProfile:
    preset: str = "default"
    fillers: bool = True
    grammar: bool = True
    punctuation: bool = True
    capitalize: bool = True
    paragraphs: bool = True
    formal: bool = False
    bullets: bool = False
    profanity: bool = False
    prompt_suffix: str = ""
    prompt_template: str = ""


@dataclass
class SafeguardSettings:
    max_recording_seconds: int = 60
    silence_cutoff_seconds: int = 3
    soft_cutoff_warning: bool = True
    confirm_long: bool = True
