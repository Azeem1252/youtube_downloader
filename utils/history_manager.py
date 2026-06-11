"""
history_manager.py
Tracks completed downloads in a local JSON history file.
"""

import json
import threading
from datetime import datetime
from pathlib import Path

HISTORY_FILE = Path.home() / ".yt_downloader_history.json"
MAX_HISTORY = 500

_history_lock = threading.RLock()


def load_history() -> list:
    """Return list of history records, newest first."""
    with _history_lock:
        if not HISTORY_FILE.exists():
            return []
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []


def add_record(record: dict) -> None:
    """
    Append a completed download record.
    record keys: title, url, filepath, quality, fmt, size_bytes, duration, date
    """
    with _history_lock:
        history = load_history()
        record.setdefault("date", datetime.now().isoformat())
        history.insert(0, record)
        # Trim to max size
        history = history[:MAX_HISTORY]
        _save(history)


def clear_history() -> None:
    """Remove all history."""
    with _history_lock:
        _save([])


def _save(history: list) -> None:
    with _history_lock:
        try:
            # Ensure parent directories exist
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"[History] Could not save history: {e}")

