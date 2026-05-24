import json
import sqlite3
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from whisprnick import config
from whisprnick.data.models import (
    CleanupProfile,
    DictationEntry,
    DictionaryWord,
    Nickname,
    Replacement,
)


class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.DB_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._migrate()
        self._cleanup_legacy()
        self._seed_defaults()

    def _cleanup_legacy(self):
        """Remove legacy OpenAI API key and cost cap settings."""
        self.conn.execute("DELETE FROM settings WHERE key = 'openai_api_key'")
        self.conn.execute("DELETE FROM settings WHERE key = 'daily_cost_cap'")
        self.conn.commit()

    def _seed_defaults(self):
        """Populate dictionary, replacements, and nicknames with defaults if empty."""
        c = self.conn.cursor()

        # Only seed if all three tables are empty
        word_count = c.execute("SELECT COUNT(*) FROM dictionary_words").fetchone()[0]
        repl_count = c.execute("SELECT COUNT(*) FROM replacements").fetchone()[0]
        nick_count = c.execute("SELECT COUNT(*) FROM nicknames").fetchone()[0]

        if word_count == 0:
            default_words = [
                ("NickWhispr", "nik-wisper"),
                ("Qwen", "queen"),
                ("Ollama", "oh-lah-mah"),
                ("OAuth", "oh-auth"),
                ("Vozi", "voh-zee"),
            ]
            c.executemany(
                "INSERT OR IGNORE INTO dictionary_words (word, pronunciation, source) VALUES (?, ?, 'default')",
                default_words,
            )

        if repl_count == 0:
            default_replacements = [
                ("nick whisper", "NickWhispr"),
                ("f y i", "FYI"),
                ("a s a p", "ASAP"),
                ("btw", "by the way"),
            ]
            c.executemany(
                "INSERT OR IGNORE INTO replacements (trigger, replacement) VALUES (?, ?)",
                default_replacements,
            )

        if nick_count == 0:
            pass

        self.conn.commit()

    def _migrate(self):
        c = self.conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS dictation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now','localtime')),
                source_app TEXT DEFAULT '',
                original_text TEXT DEFAULT '',
                cleaned_text TEXT DEFAULT '',
                cleanup_level TEXT DEFAULT 'light',
                cleanup_preset TEXT DEFAULT 'default',
                duration_seconds REAL DEFAULT 0,
                word_count INTEGER DEFAULT 0,
                filler_count INTEGER DEFAULT 0,
                fillers_found TEXT DEFAULT '',
                latency_ms INTEGER DEFAULT 0,
                cost REAL DEFAULT 0,
                whisper_model TEXT DEFAULT 'whisper-1',
                cleanup_model TEXT DEFAULT 'qwen2.5:3b'
            );

            CREATE TABLE IF NOT EXISTS dictionary_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT UNIQUE NOT NULL,
                pronunciation TEXT DEFAULT '',
                heard_count INTEGER DEFAULT 0,
                confidence INTEGER DEFAULT 0,
                source TEXT DEFAULT 'manual',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS replacements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger TEXT UNIQUE NOT NULL,
                replacement TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS nicknames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spoken TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS cleanup_profiles (
                preset TEXT PRIMARY KEY,
                config TEXT
            );
        """)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # --- Dictation History ---

    def save_dictation(self, entry: DictationEntry) -> int:
        c = self.conn.execute(
            """INSERT INTO dictation_history
               (timestamp, source_app, original_text, cleaned_text,
                cleanup_level, cleanup_preset, duration_seconds, word_count,
                filler_count, fillers_found, latency_ms, cost,
                whisper_model, cleanup_model)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                entry.timestamp.isoformat(),
                entry.source_app,
                entry.original_text,
                entry.cleaned_text,
                entry.cleanup_level,
                entry.cleanup_preset,
                entry.duration_seconds,
                entry.word_count,
                entry.filler_count,
                entry.fillers_found,
                entry.latency_ms,
                entry.cost,
                entry.whisper_model,
                entry.cleanup_model,
            ),
        )
        self.conn.commit()
        return c.lastrowid

    def _row_to_dictation(self, row: sqlite3.Row) -> DictationEntry:
        return DictationEntry(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            source_app=row["source_app"],
            original_text=row["original_text"],
            cleaned_text=row["cleaned_text"],
            cleanup_level=row["cleanup_level"],
            cleanup_preset=row["cleanup_preset"],
            duration_seconds=row["duration_seconds"],
            word_count=row["word_count"],
            filler_count=row["filler_count"],
            fillers_found=row["fillers_found"],
            latency_ms=row["latency_ms"],
            cost=row["cost"],
            whisper_model=row["whisper_model"],
            cleanup_model=row["cleanup_model"],
        )

    def get_dictation(self, id: int) -> Optional[DictationEntry]:
        row = self.conn.execute(
            "SELECT * FROM dictation_history WHERE id = ?", (id,)
        ).fetchone()
        return self._row_to_dictation(row) if row else None

    def get_recent_dictations(self, limit: int = 50) -> list[DictationEntry]:
        rows = self.conn.execute(
            "SELECT * FROM dictation_history ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_dictation(r) for r in rows]

    def search_dictations(self, query: str) -> list[DictationEntry]:
        rows = self.conn.execute(
            """SELECT * FROM dictation_history
               WHERE original_text LIKE ? OR cleaned_text LIKE ?
               ORDER BY timestamp DESC""",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
        return [self._row_to_dictation(r) for r in rows]

    def delete_dictation(self, id: int):
        self.conn.execute("DELETE FROM dictation_history WHERE id = ?", (id,))
        self.conn.commit()

    def get_dictations_today(self) -> list[DictationEntry]:
        today = datetime.now().strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT * FROM dictation_history WHERE timestamp LIKE ? ORDER BY timestamp DESC",
            (f"{today}%",),
        ).fetchall()
        return [self._row_to_dictation(r) for r in rows]

    # --- Dictionary Words ---

    def _row_to_word(self, row: sqlite3.Row) -> DictionaryWord:
        return DictionaryWord(
            id=row["id"],
            word=row["word"],
            pronunciation=row["pronunciation"],
            heard_count=row["heard_count"],
            confidence=row["confidence"],
            source=row["source"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def add_word(self, word: DictionaryWord):
        self.conn.execute(
            """INSERT OR REPLACE INTO dictionary_words
               (word, pronunciation, heard_count, confidence, source)
               VALUES (?,?,?,?,?)""",
            (word.word, word.pronunciation, word.heard_count, word.confidence, word.source),
        )
        self.conn.commit()

    def get_words(self) -> list[DictionaryWord]:
        rows = self.conn.execute(
            "SELECT * FROM dictionary_words ORDER BY word"
        ).fetchall()
        return [self._row_to_word(r) for r in rows]

    def update_word(self, word: DictionaryWord):
        self.conn.execute(
            """UPDATE dictionary_words
               SET pronunciation=?, heard_count=?, confidence=?, source=?
               WHERE id=?""",
            (word.pronunciation, word.heard_count, word.confidence, word.source, word.id),
        )
        self.conn.commit()

    def delete_word(self, id: int):
        self.conn.execute("DELETE FROM dictionary_words WHERE id = ?", (id,))
        self.conn.commit()

    def increment_heard(self, word: str):
        self.conn.execute(
            "UPDATE dictionary_words SET heard_count = heard_count + 1 WHERE word = ?",
            (word,),
        )
        self.conn.commit()

    # --- Replacements ---

    def _row_to_replacement(self, row: sqlite3.Row) -> Replacement:
        return Replacement(
            id=row["id"],
            trigger=row["trigger"],
            replacement=row["replacement"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def add_replacement(self, r: Replacement):
        self.conn.execute(
            "INSERT OR REPLACE INTO replacements (trigger, replacement) VALUES (?,?)",
            (r.trigger, r.replacement),
        )
        self.conn.commit()

    def get_replacements(self) -> list[Replacement]:
        rows = self.conn.execute(
            "SELECT * FROM replacements ORDER BY trigger"
        ).fetchall()
        return [self._row_to_replacement(r) for r in rows]

    def delete_replacement(self, id: int):
        self.conn.execute("DELETE FROM replacements WHERE id = ?", (id,))
        self.conn.commit()

    # --- Nicknames ---

    def _row_to_nickname(self, row: sqlite3.Row) -> Nickname:
        return Nickname(
            id=row["id"],
            spoken=row["spoken"],
            full_name=row["full_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def add_nickname(self, n: Nickname):
        self.conn.execute(
            "INSERT OR REPLACE INTO nicknames (spoken, full_name) VALUES (?,?)",
            (n.spoken, n.full_name),
        )
        self.conn.commit()

    def get_nicknames(self) -> list[Nickname]:
        rows = self.conn.execute(
            "SELECT * FROM nicknames ORDER BY spoken"
        ).fetchall()
        return [self._row_to_nickname(r) for r in rows]

    def delete_nickname(self, id: int):
        self.conn.execute("DELETE FROM nicknames WHERE id = ?", (id,))
        self.conn.commit()

    # --- Settings ---

    def get_setting(self, key: str, default=None):
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return default
        return json.loads(row["value"])

    def set_setting(self, key: str, value):
        self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
            (key, json.dumps(value)),
        )
        self.conn.commit()

    # --- Cleanup Profiles ---

    def get_cleanup_profile(self, preset: str) -> CleanupProfile:
        row = self.conn.execute(
            "SELECT config FROM cleanup_profiles WHERE preset = ?", (preset,)
        ).fetchone()
        if row is None:
            return CleanupProfile(preset=preset)
        data = json.loads(row["config"])
        return CleanupProfile(**data)

    def save_cleanup_profile(self, profile: CleanupProfile):
        self.conn.execute(
            "INSERT OR REPLACE INTO cleanup_profiles (preset, config) VALUES (?,?)",
            (profile.preset, json.dumps(asdict(profile))),
        )
        self.conn.commit()

    # --- Stats / Insights ---

    def _days_filter(self, days: Optional[int]) -> tuple[str, tuple]:
        if days is None:
            return "", ()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        return "WHERE timestamp >= ?", (cutoff,)

    def get_total_words(self, days: int = None) -> int:
        clause, params = self._days_filter(days)
        row = self.conn.execute(
            f"SELECT COALESCE(SUM(word_count), 0) FROM dictation_history {clause}",
            params,
        ).fetchone()
        return row[0]

    def get_total_duration(self, days: int = None) -> float:
        clause, params = self._days_filter(days)
        row = self.conn.execute(
            f"SELECT COALESCE(SUM(duration_seconds), 0) FROM dictation_history {clause}",
            params,
        ).fetchone()
        return row[0]

    def get_total_fillers(self, days: int = None) -> int:
        clause, params = self._days_filter(days)
        row = self.conn.execute(
            f"SELECT COALESCE(SUM(filler_count), 0) FROM dictation_history {clause}",
            params,
        ).fetchone()
        return row[0]

    def get_top_fillers(self, days: int = 7, limit: int = 10) -> list[tuple[str, int]]:
        clause, params = self._days_filter(days)
        rows = self.conn.execute(
            f"SELECT fillers_found FROM dictation_history {clause}",
            params,
        ).fetchall()
        counter: Counter = Counter()
        for row in rows:
            raw = row[0]
            if raw:
                for filler in raw.split(","):
                    filler = filler.strip()
                    if filler:
                        counter[filler] += 1
        return counter.most_common(limit)

    def get_app_usage(self, days: int = 7) -> list[tuple[str, int]]:
        clause, params = self._days_filter(days)
        rows = self.conn.execute(
            f"""SELECT source_app, SUM(word_count) as total
                FROM dictation_history {clause}
                GROUP BY source_app ORDER BY total DESC""",
            params,
        ).fetchall()
        return [(row[0], row[1]) for row in rows]

    def get_daily_activity(self, days: int = 7) -> list[tuple[str, float]]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self.conn.execute(
            """SELECT DATE(timestamp) as day, SUM(duration_seconds) / 60.0 as mins
               FROM dictation_history
               WHERE timestamp >= ?
               GROUP BY day ORDER BY day""",
            (cutoff,),
        ).fetchall()
        return [(row[0], round(row[1], 2)) for row in rows]

