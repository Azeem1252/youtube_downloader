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
_cache_initialized = False
_last_checked_custom_path: Optional[str] = None
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
    global _resolved_ffmpeg_path, _last_checked_custom_path, _cache_initialized

    custom_path = custom_path.strip('\'" \t')

    # If the custom path is a directory, try to locate ffmpeg inside it or its bin/ subfolder
    if custom_path and os.path.isdir(custom_path):
        found = False
        for name in ("ffmpeg.exe", "ffmpeg"):
            p1 = os.path.join(custom_path, name)
            if os.path.isfile(p1) and _try_run(p1):
                custom_path = p1
                found = True
                break
            p2 = os.path.join(custom_path, "bin", name)
            if os.path.isfile(p2) and _try_run(p2):
                custom_path = p2
                found = True
                break
        if not found:
            pass

    if _cache_initialized and _last_checked_custom_path == custom_path:
        return _resolved_ffmpeg_path

    # Perform resolution
    resolved = None
    if custom_path and _try_run(custom_path):
        resolved = custom_path
    elif _try_run("ffmpeg"):
        resolved = "ffmpeg"
    else:
        bundled = _get_imageio_ffmpeg_path()
        if bundled and _try_run(bundled):
            resolved = bundled

    _last_checked_custom_path = custom_path
    _resolved_ffmpeg_path = resolved
    _cache_initialized = True
    return resolved


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
    resolved = resolve_ffmpeg(ffmpeg_path)
    if not resolved:
        return False, (
            "[!] FFmpeg not detected yet -- imageio-ffmpeg will attempt to download it automatically "
            "on first use.\n"
            "If downloads fail, install manually:\n"
            "  Windows:  winget install ffmpeg\n"
            "  URL:      https://ffmpeg.org/download.html"
        )

    version = _try_run(resolved) or "unknown version"
    cleaned_path = ffmpeg_path.strip('\'" \t')

    if cleaned_path:
        is_custom = False
        if os.path.isdir(cleaned_path):
            try:
                # Check if resolved file is inside the cleaned_path directory
                p_cleaned = os.path.abspath(cleaned_path)
                p_resolved = os.path.abspath(resolved)
                is_custom = os.path.commonpath([p_cleaned, p_resolved]) == os.path.commonpath([p_cleaned])
            except Exception:
                pass
        else:
            is_custom = (os.path.abspath(resolved) == os.path.abspath(cleaned_path))

        if is_custom:
            return True, f"[OK] Custom path: {version}\nResolved binary: {resolved}"

    if resolved == "ffmpeg":
        return True, f"[OK] System: {version}"

    bundled = _get_imageio_ffmpeg_path()
    if bundled and resolved == bundled:
        return True, f"[OK] Auto-bundled (imageio-ffmpeg): {version}\nPath: {resolved}"

    return True, f"[OK] FFmpeg: {version}\nPath: {resolved}"


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
