"""
ffmpeg_checker.py
Detects FFmpeg — tries:
  1. A user-specified custom path
  2. The system PATH (already installed by user)
  3. imageio-ffmpeg bundled binaries (auto-downloaded on first use)

This means the app works out-of-the-box with NO manual FFmpeg installation.
"""

import subprocess
import os
from typing import Optional

# Cache the resolved path so we don't re-check every call
_resolved_ffmpeg_path: Optional[str] = None
_resolved_ffprobe_path: Optional[str] = None


def _try_run(cmd: str) -> Optional[str]:
    """Run `cmd -version` and return the first line if successful."""
    try:
        result = subprocess.run(
            [cmd, "-version"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if result.returncode == 0:
            return result.stdout.splitlines()[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _get_imageio_ffmpeg_path() -> Optional[str]:
    """Return the FFmpeg binary path bundled by imageio-ffmpeg, or None."""
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.isfile(path):
            return path
    except Exception:
        pass
    return None


def resolve_ffmpeg(custom_path: str = "") -> Optional[str]:
    """
    Return a working ffmpeg executable path, trying in order:
      1. custom_path (user-specified in Settings)
      2. System PATH 'ffmpeg'
      3. imageio-ffmpeg bundled binary
    Returns None if all fail.
    """
    global _resolved_ffmpeg_path

    # 1. Custom path
    if custom_path and _try_run(custom_path):
        _resolved_ffmpeg_path = custom_path
        return custom_path

    # 2. System PATH
    if _try_run("ffmpeg"):
        _resolved_ffmpeg_path = "ffmpeg"
        return "ffmpeg"

    # 3. imageio-ffmpeg bundled binary
    bundled = _get_imageio_ffmpeg_path()
    if bundled and _try_run(bundled):
        _resolved_ffmpeg_path = bundled
        return bundled

    _resolved_ffmpeg_path = None
    return None


def get_ffmpeg_version(ffmpeg_path: str = "") -> Optional[str]:
    """Return ffmpeg version string if found (any source), else None."""
    path = resolve_ffmpeg(ffmpeg_path)
    if path:
        return _try_run(path)
    return None


def is_ffmpeg_available(ffmpeg_path: str = "") -> bool:
    """Return True if ffmpeg is available from any source."""
    return resolve_ffmpeg(ffmpeg_path) is not None


def ffmpeg_status_message(ffmpeg_path: str = "") -> tuple[bool, str]:
    """
    Returns (available: bool, message: str) for UI display.
    Detects the source of FFmpeg and reports it clearly.
    """
    # Custom path
    if ffmpeg_path and _try_run(ffmpeg_path):
        version = _try_run(ffmpeg_path)
        return True, f"[OK] Custom path: {version}"

    # System PATH
    sys_ver = _try_run("ffmpeg")
    if sys_ver:
        return True, f"[OK] System: {sys_ver}"

    # imageio-ffmpeg bundled
    bundled = _get_imageio_ffmpeg_path()
    if bundled:
        bundled_ver = _try_run(bundled)
        if bundled_ver:
            return True, f"[OK] Auto-bundled (imageio-ffmpeg): {bundled_ver}"

    return False, (
        "[!] FFmpeg not detected yet -- imageio-ffmpeg will attempt to download it automatically "
        "on first use.\n"
        "If downloads fail, install manually:\n"
        "  Windows:  winget install ffmpeg\n"
        "  URL:      https://ffmpeg.org/download.html"
    )


def get_ffmpeg_location_for_ytdlp(custom_path: str = "") -> Optional[str]:
    """
    Returns the FULL PATH to the ffmpeg binary for yt-dlp's 'ffmpeg_location'.
    yt-dlp accepts either a directory (only works if binary is named ffmpeg.exe)
    or a full path to the binary itself.
    imageio-ffmpeg bundles 'ffmpeg-win-x86_64-v7.1.exe' — NOT 'ffmpeg.exe' —
    so we MUST pass the full path, not the directory.
    Returns None if ffmpeg is on the system PATH (yt-dlp finds it automatically).
    """
    path = resolve_ffmpeg(custom_path)
    if not path or path == "ffmpeg":
        return None  # Already on PATH — yt-dlp finds it automatically
    # Full path to the binary (works for imageio-ffmpeg bundled binaries)
    return path
