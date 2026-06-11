"""
settings_manager.py
Handles loading and saving user preferences to a JSON file.
"""

import json
import os
import threading
from pathlib import Path

SETTINGS_FILE = Path.home() / ".yt_downloader_settings.json"

DEFAULT_SETTINGS = {
    "output_dir": str(Path.home() / "Downloads"),
    "default_quality": "1080p",
    "default_format": "mp4",
    "default_codec": "h264",
    "default_audio_quality": "192",
    "subtitle_lang": "en",
    "embed_subtitles": False,
    "write_subtitles": True,
    "auto_subtitles": True,
    "concurrent_downloads": 2,
    "proxy": "",
    "rate_limit": "",
    "ffmpeg_path": "",
    "organize_by_channel": False,
    "avoid_duplicates": True,
    "filename_template": "%(title)s.%(ext)s",
    "theme": "dark",
    "color_theme": "blue",
    "last_tab": 0,
    "cookies_browser": "",
}

_settings_lock = threading.RLock()


def load_settings() -> dict:
    """Load settings from disk, merging with defaults for any missing keys."""
    with _settings_lock:
        settings = DEFAULT_SETTINGS.copy()
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                settings.update(saved)
            except (json.JSONDecodeError, OSError):
                pass
        return settings


def save_settings(settings: dict) -> None:
    """Persist settings to disk."""
    with _settings_lock:
        try:
            # Ensure the directory exists
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
        except OSError as e:
            print(f"[Settings] Could not save settings: {e}")


def reset_settings() -> dict:
    """Reset settings to defaults and save."""
    with _settings_lock:
        if SETTINGS_FILE.exists():
            try:
                SETTINGS_FILE.unlink()
            except OSError:
                pass
        return DEFAULT_SETTINGS.copy()

