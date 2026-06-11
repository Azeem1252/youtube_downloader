"""
downloader.py  —  YT Downloader Pro core engine
=================================================
Fixes in this version:
  • Corrected yt-dlp format selector strings (no more .f399 partial streams)
  • FFmpeg full binary path passed correctly (merging now works)
  • ignoreerrors=False so FFmpeg failures are visible
  • Auto-pause / auto-resume on internet loss (ConnectivityMonitor integration)
  • Sequential playlist downloading with archive-based per-video resume
"""

import os
import re
import threading
import uuid
from pathlib import Path
from typing import Callable, List, Optional

import yt_dlp

from utils.ffmpeg_checker import get_ffmpeg_location_for_ytdlp
from utils.connectivity import monitor as connectivity_monitor


# ─────────────────────────────────────────────────────────────────────────────
# Constants / maps
# ─────────────────────────────────────────────────────────────────────────────
QUALITY_MAP = {
    "Best":  None,      # No height filter — let yt-dlp pick highest
    "4K":    2160,
    "1440p": 1440,
    "1080p": 1080,
    "720p":  720,
    "480p":  480,
    "360p":  360,
    "240p":  240,
    "144p":  144,
}

AUDIO_QUALITY_MAP = {
    "Best":    "0",
    "320kbps": "0",
    "256kbps": "2",
    "192kbps": "4",
    "128kbps": "5",
    "64kbps":  "9",
}

FORMAT_EXT_MAP = {
    "mp4": "mp4", "mkv": "mkv", "webm": "webm",
    "mp3": "mp3", "m4a": "m4a", "flac": "flac", "wav": "wav",
}

AUDIO_FORMATS = {"mp3", "m4a", "flac", "wav"}

_CODEC_PREF = {
    "h264": "avc1",
    "h265": "hev1",
    "vp9":  "vp09",
    "av1":  "av01",
}

# Keywords that suggest a network-level failure (not a content error)
_NET_KEYWORDS = {
    "connection", "network", "timed out", "timeout", "reset",
    "unreachable", "no route", "socket", "errno", "getaddrinfo",
    "name or service not known", "ssl", "http error 5",
    "read error", "connection refused", "broken pipe",
}


# ─────────────────────────────────────────────────────────────────────────────
# Format string builder  (FIXED — no more malformed selectors)
# ─────────────────────────────────────────────────────────────────────────────
def _build_format_string(quality: str, codec: str, is_audio: bool, fmt: str) -> str:
    """
    2026-updated format string.
    Uses bv*/ba selectors which are more robust with YouTube's 2026
    SABR / PO-Token changes. Prefers mp4+m4a containers for compatibility.

    Examples:
      1080p H.264:  bv*[height<=1080][ext=mp4][vcodec^=avc1]+ba[ext=m4a]/
                    bv*[height<=1080][ext=mp4]+ba/bv*[height<=1080]+ba/b[height<=1080]
      Audio-only:   ba[ext=m4a]/ba/b
    """
    if is_audio:
        # Prefer m4a for audio (YouTube's native audio format, best quality)
        if fmt == "m4a":
            return "ba[ext=m4a]/ba/b"
        return "ba/b"

    # Height constraint
    max_h = QUALITY_MAP.get(quality)
    h_filter = f"[height<={max_h}]" if max_h else ""

    # Codec preference filter
    cpref = _CODEC_PREF.get(codec, "")
    c_filter = f"[vcodec^={cpref}]" if cpref else ""

    # 2026 recommended format order:
    # 1. Best: mp4 video + m4a audio (native YouTube containers, fastest CDN)
    # 2. Fallback: mp4 video + any audio
    # 3. Fallback: any video + any audio (merged)
    # 4. Final: any single combined stream
    return (
        f"bv*{h_filter}[ext=mp4]{c_filter}+ba[ext=m4a]/"
        f"bv*{h_filter}[ext=mp4]+ba/"
        f"bv*{h_filter}+ba/"
        f"b{h_filter}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Network error helper
# ─────────────────────────────────────────────────────────────────────────────
def _is_network_error(exc: Exception) -> bool:
    """Heuristic: True when exception looks like a connectivity failure."""
    msg = str(exc).lower()
    return any(kw in msg for kw in _NET_KEYWORDS)


# ─────────────────────────────────────────────────────────────────────────────
# DownloadItem  —  represents one queued download job
# ─────────────────────────────────────────────────────────────────────────────
class DownloadItem:
    STATUS_QUEUED      = "Queued"
    STATUS_FETCHING    = "Fetching info…"
    STATUS_DOWNLOADING = "Downloading"
    STATUS_MERGING     = "Merging streams…"
    STATUS_CONVERTING  = "Converting…"
    STATUS_NO_INTERNET = "No Internet…"
    STATUS_RESUMING    = "Resuming…"
    STATUS_DONE        = "Done"
    STATUS_ERROR       = "Error"
    STATUS_CANCELLED   = "Cancelled"

    def __init__(self, url: str, opts: dict, item_id: str):
        self.url      = url
        self.opts     = opts
        self.item_id  = item_id
        self.title    = url
        self.status   = self.STATUS_QUEUED
        self.percent  = 0.0
        self.speed    = ""
        self.eta      = ""
        self.filepath = ""
        self.error    = ""
        self._cancel  = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # Used externally to attach display metadata
        self._quality = ""
        self._fmt     = ""

    def cancel(self):   self._cancel.set()

    @property
    def is_cancelled(self): return self._cancel.is_set()


# ─────────────────────────────────────────────────────────────────────────────
# PlaylistJob  —  sequential playlist with archive-based resume
# ─────────────────────────────────────────────────────────────────────────────
class PlaylistJob:
    """
    Downloads every video in a playlist one-by-one, in order.
    Uses a yt-dlp archive file so already-completed videos are
    skipped automatically — even after the app is restarted.
    """

    STATUS_FETCHING    = "Fetching playlist…"
    STATUS_DOWNLOADING = "Downloading"
    STATUS_NO_INTERNET = "No Internet…"
    STATUS_RESUMING    = "Resuming…"
    STATUS_DONE        = "Done"
    STATUS_ERROR       = "Error"
    STATUS_CANCELLED   = "Cancelled"

    def __init__(self, url: str, base_opts: dict, item_id: str):
        self.url          = url
        self.base_opts    = base_opts   # from build_ydl_opts (no URL baked in)
        self.item_id      = item_id
        self.title        = "Playlist…"
        self.status       = self.STATUS_FETCHING
        self.entries: List[dict] = []   # {"url": ..., "title": ..., "index": N}
        self.total        = 0
        self.current_index = 0          # 0-based
        self.percent      = 0.0         # overall playlist progress
        self.current_item: Optional[DownloadItem] = None
        self.archive_path = ""          # written by yt-dlp; persists between runs
        self._cancel      = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def cancel(self):
        self._cancel.set()
        if self.current_item:
            self.current_item.cancel()

    @property
    def is_cancelled(self): return self._cancel.is_set()

    @property
    def current_video_title(self) -> str:
        if self.current_item:
            return self.current_item.title
        return ""

    @property
    def current_video_percent(self) -> float:
        if self.current_item:
            return self.current_item.percent
        return 0.0

    @property
    def current_video_speed(self) -> str:
        if self.current_item:
            return self.current_item.speed
        return ""

    @property
    def current_video_eta(self) -> str:
        if self.current_item:
            return self.current_item.eta
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Video info fetching
# ─────────────────────────────────────────────────────────────────────────────
def fetch_info(url: str, ffmpeg_path: str = "", cookies_browser: str = "", proxy: str = "") -> dict:
    """Extract video/playlist metadata without downloading."""
    ydl_opts = {
        "quiet":        True,
        "no_warnings":  True,
        "skip_download": True,
        "noplaylist":   False,
        "extractor_args": {
            "youtube": {
                "player_client": ["default", "-android_sdkless"],
            }
        },
    }
    loc = get_ffmpeg_location_for_ytdlp(ffmpeg_path)
    if loc:
        ydl_opts["ffmpeg_location"] = loc
    if cookies_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_browser,)
    if proxy:
        ydl_opts["proxy"] = proxy

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def get_available_subtitle_langs(info: dict) -> list:
    langs = set()
    for lang in info.get("subtitles", {}).keys():
        langs.add(lang)
    for lang in info.get("automatic_captions", {}).keys():
        langs.add(lang)
    return sorted(langs)


def get_playlist_entries(info: dict) -> list:
    """Return ordered list of {url, title, index} dicts from a playlist info dict."""
    entries = []
    raw = info.get("entries") or []
    for i, entry in enumerate(raw):
        if entry:
            entries.append({
                "url":   entry.get("webpage_url") or entry.get("url", ""),
                "title": entry.get("title", f"Video {i+1}"),
                "index": i,
            })
    return entries


# ─────────────────────────────────────────────────────────────────────────────
# Options builder  (FIXED)
# ─────────────────────────────────────────────────────────────────────────────
def build_ydl_opts(
    output_dir:           str,
    quality:              str  = "Best",
    fmt:                  str  = "mp4",
    codec:                str  = "h264",
    audio_quality:        str  = "Best",
    subtitle_langs:       Optional[List[str]] = None,
    embed_subs:           bool = False,
    write_subs:           bool = True,
    auto_subs:            bool = True,
    proxy:                str  = "",
    rate_limit:           str  = "",
    ffmpeg_path:          str  = "",
    organize_by_channel:  bool = False,
    avoid_duplicates:     bool = True,
    filename_template:    str  = "%(title)s.%(ext)s",
    playlist:             bool = False,
    archive_path:         str  = "",
    # 2026: browser name to pull cookies from ("chrome","firefox","edge","opera","brave")
    cookies_browser:      str  = "",
    progress_hook:        Optional[Callable] = None,
) -> dict:
    """Build a valid yt-dlp options dict."""

    is_audio = fmt in AUDIO_FORMATS

    # Output template
    if organize_by_channel:
        outtmpl = os.path.join(output_dir, "%(uploader)s", filename_template)
    else:
        outtmpl = os.path.join(output_dir, filename_template)

    # ── FIXED format string ───────────────────────────────────────────
    format_str = _build_format_string(quality, codec, is_audio, fmt)

    opts: dict = {
        "format":        format_str,
        "outtmpl":       outtmpl,
        "quiet":         True,
        "no_warnings":   True,
        "noplaylist":    not playlist,
        # Do NOT ignore errors — FFmpeg/merge failures must be visible
        "ignoreerrors":  False,
        # FIXED: correct Python API key is 'continuedl' (NOT 'continue_dl')
        # This enables resuming partial .part files after network interruption
        "continuedl":    True,
        # FIXED: 'nooverwrites' is deprecated; correct key is 'overwrites'
        "overwrites":    not avoid_duplicates,
        # ── Performance & Reliability ─────────────────────────────────
        # Parallel fragment downloads — huge speed improvement for DASH/HLS
        "concurrent_fragment_downloads": 4,
        # Built-in yt-dlp retry logic for transient failures
        "retries":            10,
        "fragment_retries":   10,
        "file_access_retries": 5,
        # Detect hung connections quickly (seconds)
        "socket_timeout":     15,
        # Large chunk size for more stable HTTP downloads
        "http_chunk_size":    10_485_760,   # 10 MB
        # ── 2026 YouTube compatibility ──────────────────────────────
        # player_client=default,-android_sdkless handles SABR/PO-Token changes
        "extractor_args": {
            "youtube": {
                "player_client": ["default", "-android_sdkless"],
            }
        },
        # FFmpeg reconnect args — keeps streams alive through brief drops
        "external_downloader_args": {
            "ffmpeg_i1": ["-reconnect", "1",
                          "-reconnect_streamed", "1",
                          "-reconnect_delay_max", "5"]
        },
        "postprocessors": [],
        "writethumbnail": False,
    }

    # ── 2026: Browser cookies (bypasses YouTube throttling & bot detection) ──
    if cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser,)

    # ── FFmpeg location (FIXED: full binary path, not directory) ───────
    loc = get_ffmpeg_location_for_ytdlp(ffmpeg_path)
    if loc:
        opts["ffmpeg_location"] = loc

    if proxy:       opts["proxy"]     = proxy
    if rate_limit:  opts["ratelimit"] = rate_limit
    if archive_path: opts["download_archive"] = archive_path

    # ── Merge output format (FIXED: always set for video) ─────────────
    if not is_audio:
        merge_fmt = fmt if fmt in ("mp4", "mkv", "webm") else "mp4"
        opts["merge_output_format"] = merge_fmt
        opts["keepvideo"] = False  # Don't keep intermediate streams

    # ── Audio conversion post-processor ───────────────────────────────
    if is_audio:
        aq = AUDIO_QUALITY_MAP.get(audio_quality, "4")
        audio_codec_map = {"mp3": "mp3", "m4a": "m4a", "flac": "flac", "wav": "wav"}
        opts["postprocessors"].append({
            "key": "FFmpegExtractAudio",
            "preferredcodec":   audio_codec_map.get(fmt, "mp3"),
            "preferredquality": aq,
        })

    # ── Subtitles ─────────────────────────────────────────────────────
    if subtitle_langs:
        opts["writesubtitles"]   = write_subs
        opts["writeautomaticsub"] = auto_subs
        opts["subtitleslangs"]   = subtitle_langs
        opts["embedsubs"]        = embed_subs
        if embed_subs:
            opts["postprocessors"].append({"key": "FFmpegEmbedSubtitle"})

    # ── Metadata ──────────────────────────────────────────────────────
    opts["postprocessors"].append({"key": "FFmpegMetadata"})

    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    return opts


# ─────────────────────────────────────────────────────────────────────────────
# Core download with auto-pause / auto-resume on internet loss
# ─────────────────────────────────────────────────────────────────────────────
def _run_ydl(item: DownloadItem, ydl_opts: dict, on_progress: Optional[Callable[[DownloadItem], None]] = None) -> None:
    """Execute yt-dlp download for a single item synchronously."""

    _fmt_code_re = re.compile(r'\.f\d+$')

    def hook(d):
        if item.is_cancelled:
            raise yt_dlp.utils.DownloadCancelled("Cancelled by user")

        status = d.get("status", "")
        if status == "downloading":
            total   = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            dlbytes = d.get("downloaded_bytes", 0)
            item.percent = (dlbytes / total * 100) if total else 0
            item.speed   = _fmt_speed(d.get("speed") or 0)
            item.eta     = _fmt_eta(d.get("eta"))
            item.status  = DownloadItem.STATUS_DOWNLOADING
            # Update title from info_dict if yt-dlp provides it (no extra fetch)
            info_dict = d.get("info_dict", {})
            real_title = info_dict.get("title", "")
            if real_title:
                item.title = real_title
        elif status == "finished":
            item.percent  = 100
            item.status   = DownloadItem.STATUS_MERGING
            filepath = d.get("filename", "")
            # Strip yt-dlp temp format codes (.f399, .f140) from displayed name
            if filepath:
                item.filepath = filepath
                stem = _fmt_code_re.sub("", Path(filepath).stem)
                if stem and not stem.startswith("."):
                    item.title = stem

        if on_progress:
            on_progress(item)

    ydl_opts_copy = dict(ydl_opts)
    ydl_opts_copy["progress_hooks"] = [hook]

    # FIXED: Go straight to download — NO separate extract_info() call.
    # yt-dlp's download() does its own internal extraction automatically.
    # Calling extract_info() first was causing a 3-4 minute double-fetch.
    if item.is_cancelled:
        raise yt_dlp.utils.DownloadCancelled("Cancelled")

    # Show 'Preparing' during yt-dlp's internal info extraction phase
    # (before progress hook fires with actual bytes)
    item.status = DownloadItem.STATUS_FETCHING
    with yt_dlp.YoutubeDL(ydl_opts_copy) as ydl:
        ydl.download([item.url])


def download_item(
    item: DownloadItem,
    on_progress: Optional[Callable[[DownloadItem], None]] = None,
    on_complete: Optional[Callable[[DownloadItem], None]] = None,
) -> None:
    """
    Download a single item with automatic pause/resume on internet loss.
    Calls on_progress from this (download) thread — callers must marshal to UI thread.
    """

    def _notify():
        if on_progress:
            on_progress(item)

    item.status = DownloadItem.STATUS_FETCHING
    _notify()

    MAX_RETRIES = 9999  # Effectively infinite — we only stop on cancel or real error

    for attempt in range(MAX_RETRIES):
        if item.is_cancelled:
            item.status = DownloadItem.STATUS_CANCELLED
            break

        # ── Wait for internet before each attempt ─────────────────────
        if not connectivity_monitor.is_connected:
            item.status = DownloadItem.STATUS_NO_INTERNET
            item.speed  = ""
            item.eta    = ""
            _notify()
            connectivity_monitor.wait_for_connection()
            if item.is_cancelled:
                item.status = DownloadItem.STATUS_CANCELLED
                break
            item.status = DownloadItem.STATUS_RESUMING
            _notify()

        try:
            _run_ydl(item, item.opts, on_progress=on_progress)
            item.status  = DownloadItem.STATUS_DONE
            item.percent = 100
            _notify()
            break  # ✓ success

        except yt_dlp.utils.DownloadCancelled:
            item.status = DownloadItem.STATUS_CANCELLED
            break

        except Exception as exc:
            # If internet dropped during download → wait and retry
            if not connectivity_monitor.is_connected or _is_network_error(exc):
                item.status = DownloadItem.STATUS_NO_INTERNET
                item.speed  = ""
                item.eta    = ""
                _notify()
                connectivity_monitor.wait_for_connection()
                if item.is_cancelled:
                    item.status = DownloadItem.STATUS_CANCELLED
                    break
                item.status  = DownloadItem.STATUS_RESUMING
                # Do NOT reset percent — continuedl=True resumes from the partial file
                _notify()
                continue  # retry

            # Real error (not connectivity)
            item.status = DownloadItem.STATUS_ERROR
            item.error  = str(exc)
            print(f"[Downloader] Error on '{item.title}': {exc}")
            break

    if on_complete:
        on_complete(item)


def start_download_thread(
    item: DownloadItem,
    on_progress: Optional[Callable[[DownloadItem], None]] = None,
    on_complete: Optional[Callable[[DownloadItem], None]] = None,
) -> threading.Thread:
    """Spawn a daemon thread for the given DownloadItem."""
    t = threading.Thread(
        target=download_item,
        args=(item, on_progress, on_complete),
        daemon=True,
    )
    item._thread = t
    t.start()
    return t


# ─────────────────────────────────────────────────────────────────────────────
# Sequential playlist download
# ─────────────────────────────────────────────────────────────────────────────
def _playlist_archive_path(output_dir: str, playlist_id: str) -> str:
    """Return path to the yt-dlp archive file for this playlist."""
    safe_id = "".join(c for c in playlist_id if c.isalnum() or c in "-_")[:64]
    return os.path.join(output_dir, f".ytdlp_archive_{safe_id}.txt")


def run_playlist_job(
    job:         PlaylistJob,
    on_progress: Optional[Callable[[PlaylistJob], None]] = None,
    on_complete: Optional[Callable[[PlaylistJob], None]] = None,
) -> None:
    """
    Run a PlaylistJob synchronously (call from a thread).
    Downloads videos one-by-one in playlist order.
    Skips already-downloaded videos via archive file (resume safe).
    Pauses automatically on internet loss; resumes when connection returns.
    """

    def _notify():
        if on_progress:
            on_progress(job)

    # ── 1. Fetch playlist info ────────────────────────────────────────
    job.status = PlaylistJob.STATUS_FETCHING
    _notify()

    if not connectivity_monitor.is_connected:
        job.status = PlaylistJob.STATUS_NO_INTERNET
        _notify()
        connectivity_monitor.wait_for_connection()

    opts_cookies = job.base_opts.get("cookiesfrombrowser")
    cookies_browser = opts_cookies[0] if (opts_cookies and isinstance(opts_cookies, tuple)) else ""
    proxy = job.base_opts.get("proxy", "")
    ffmpeg_loc = job.base_opts.get("ffmpeg_location", "")

    try:
        info = fetch_info(job.url, ffmpeg_path=ffmpeg_loc, cookies_browser=cookies_browser, proxy=proxy)
    except Exception as exc:
        job.status = PlaylistJob.STATUS_ERROR
        if on_complete:
            on_complete(job)
        return

    if job.is_cancelled:
        job.status = PlaylistJob.STATUS_CANCELLED
        if on_complete:
            on_complete(job)
        return

    job.title   = info.get("title") or info.get("playlist_title") or "Playlist"
    job.entries = get_playlist_entries(info)
    job.total   = len(job.entries)

    if not job.entries:
        job.status = PlaylistJob.STATUS_ERROR
        if on_complete:
            on_complete(job)
        return

    # ── 2. Set up archive file for resume ─────────────────────────────
    playlist_id = info.get("id") or info.get("playlist_id") or str(uuid.uuid4())[:8]
    output_dir  = job.base_opts.get("_output_dir", ".")
    job.archive_path = _playlist_archive_path(output_dir, playlist_id)

    # ── 3. Download each video in order ──────────────────────────────
    for idx, entry in enumerate(job.entries):
        if job.is_cancelled:
            break

        job.current_index = idx
        job.percent = (idx / job.total) * 100
        _notify()

        # Build per-video opts with archive file (auto-skip completed videos)
        video_opts = dict(job.base_opts)
        video_opts["download_archive"] = job.archive_path
        video_opts.pop("_output_dir", None)

        item_id = f"{job.item_id}_v{idx}"
        item = DownloadItem(entry["url"], video_opts, item_id)
        item.title    = entry["title"]
        item._quality = video_opts.get("_quality", "")
        item._fmt     = video_opts.get("_fmt", "")
        job.current_item = item

        def _video_progress(it):
            _notify()

        # download_item handles its own internet-loss retry loop
        download_item(item, on_progress=_video_progress)

        if item.status == DownloadItem.STATUS_CANCELLED:
            job.status = PlaylistJob.STATUS_CANCELLED
            break

    # ── 4. Finish ────────────────────────────────────────────────────
    if not job.is_cancelled:
        job.status  = PlaylistJob.STATUS_DONE
        job.percent = 100
    job.current_item = None
    _notify()

    if on_complete:
        on_complete(job)


def start_playlist_thread(
    job:         PlaylistJob,
    on_progress: Optional[Callable[[PlaylistJob], None]] = None,
    on_complete: Optional[Callable[[PlaylistJob], None]] = None,
) -> threading.Thread:
    """Spawn a daemon thread for the given PlaylistJob."""
    t = threading.Thread(
        target=run_playlist_job,
        args=(job, on_progress, on_complete),
        daemon=True,
    )
    job._thread = t
    t.start()
    return t


# ─────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────────────────────
def _fmt_speed(bps: float) -> str:
    if bps <= 0: return "—"
    if bps >= 1_000_000: return f"{bps/1_000_000:.1f} MB/s"
    if bps >= 1_000:     return f"{bps/1_000:.0f} KB/s"
    return f"{bps:.0f} B/s"


def _fmt_eta(seconds) -> str:
    if seconds is None: return "—"
    s = int(seconds)
    if s >= 3600: return f"{s//3600}h {(s%3600)//60}m"
    if s >= 60:   return f"{s//60}m {s%60}s"
    return f"{s}s"


def fmt_size(size_bytes: Optional[int]) -> str:
    if size_bytes is None: return "—"
    if size_bytes >= 1_073_741_824: return f"{size_bytes/1_073_741_824:.1f} GB"
    if size_bytes >= 1_048_576:     return f"{size_bytes/1_048_576:.1f} MB"
    if size_bytes >= 1_024:         return f"{size_bytes/1_024:.1f} KB"
    return f"{size_bytes} B"


def fmt_duration(seconds: Optional[int]) -> str:
    if seconds is None: return "—"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"
