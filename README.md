# YT Downloader Pro

A powerful, modern desktop application for downloading YouTube videos and playlists with full control over quality, formats, subtitles, and queue management. Built using Python, CustomTkinter, and `yt-dlp`.

**FFmpeg is automatically handled** — no manual installation required. The app automatically bundles and locates FFmpeg binaries.

---

## 📸 Interface Preview & Design
The application features a premium **Left Sidebar Navigation** design using a deep space color scheme (`#080c14` sidebar, `#0b0f19` main container, `#111625` content cards) with custom neon indicator states and soft-colored badges.

---

## ✨ Features

- 🎬 **Any Video Resolution**: 4K, 1440p, 1080p, 720p, 480p, 360p, 240p, 144p, or Best.
- 🎵 **Audio Conversion**: Extract audio as MP3, M4A, FLAC, or WAV with selectable bitrates (Best down to 64kbps).
- 📝 **Subtitles & Captions**: Download subtitles for any language, toggle soft-coded embedding (selectable in VLC), or fallback to auto-generated transcripts.
- 🖼️ **Rich Metadata Previews**: Fetches and displays thumbnail, video title, uploader channel, duration, and view counts before starting.
- 🔁 **Sequential Playlists**: Playlist Mode downloads videos one-by-one, skipping already-completed tracks automatically (resumable after app restart).
- 🔌 **Connectivity Monitor**: Automatically pauses the download queue when internet drops out and resumes where it left off once connectivity is restored.
- 🚫 **Duplicate Prevention**: Prevents double-download conflicts and file locking (`Access is denied` / WinError 5) by checking active entries in the queue.
- 🍪 **Bypass Throttling (2026 Support)**: Integrates active browser cookies session extraction (Chrome, Firefox, Edge, Brave, etc.) to bypass YouTube's HTTP 403 blocks and severe download throttling.
- 📊 **Active Download Queue**: Real-time progress bars, speed, ETA, status indicators, and cancellation actions.
- 🕓 **Searchable History Log**: Displays completed downloads with real-time text-filtering search and a **▶ Play** button that opens files directly in your media player.
- ⚙️ **Custom Settings**: Proxies, download rate limits, parallel download threads, and customized output folder templates.

---

## 🛠️ Installation

### 1. Install Python (Version 3.10+)
Ensure Python 3.10 or newer is installed on your system. Download it from [python.org](https://www.python.org/).

### 2. Download Project Files
Clone or download the project files. Open your terminal/PowerShell inside the project directory:

```bash
cd youtube_downloader
```

### 3. Install Requirements
Install the required Python modules using `pip`:

```bash
pip install -r requirements.txt
```

This automatically installs:
- `yt-dlp` — Core download engine
- `customtkinter` — UI frame library
- `Pillow` — Image thumbnail handling
- `requests` — Fetching online assets
- `imageio-ffmpeg` — Auto-bundled FFmpeg engine

---

## 🚀 How to Run

Launch the application by executing `main.py`:

```bash
python main.py
```

---

## 📖 How to Use

1. **Enter URL**: Paste a YouTube video or playlist link into the omnibar and press **Enter** (or click **Fetch Info**).
2. **Review Info**: Look at the metadata card (badges display uploader, duration, and views).
3. **Configure Options**:
   - **Quality Target**: From 4K down to 144p.
   - **Format**: Select video format (MP4/MKV/WebM) or audio-only formats (MP3/M4A/FLAC/WAV).
   - **Subtitles**: Toggle subtitle downloading, select language, or choose to embed it as a soft-coded track.
4. **Choose Destination**: Select where to save files. By default, it saves to your user `Downloads` directory.
5. **Download**: Click **Download Now**. You can monitor speed, status, and ETA on the **Queue** panel.
6. **Access completed downloads**: Open the **History** panel. Search for past files by title, or click **▶ Play** to open them immediately.

---

## ⚙️ Options Reference

| Option Section | Parameter | Description |
|---|---|---|
| **Directories** | Output Folder | Where videos are saved |
| | Filename Template | yt-dlp format e.g. `%(title)s.%(ext)s` |
| | Organize by Channel | Auto-sorts videos into directories by channel name |
| | Skip Duplicates | Skips downloading files that already exist in the target folder |
| **Subtitles** | Download Subtitles | Downloads subtitle track (Toggled **ON** by default) |
| | Embed in File | Soft-embeds subtitles into the container (Toggled **OFF** by default) |
| | Auto-captions | Falls back to YouTube speech-recognition transcripts |
| **Network** | Browser Cookies | Uses active cookie files to bypass throttling & captchas |
| | Proxy | Direct downloads through an HTTP/SOCKS5 server |
| | Rate Limit | Throttle speed limit e.g. `2M` (2 MB/s) |
| **System** | FFmpeg Path | Path to manual binary, or leaves empty to use auto-bundling |
| | Color Theme | Dark / Light / System (follows OS appearance setting) |

---

## 💬 Troubleshooting

### Download stuck or speeds are very slow?
YouTube actively throttles unauthenticated downloads. Go to the **Settings** panel, set **Browser cookies** to your active browser (e.g. `chrome` or `firefox`), and click **Save Settings**. This authenticates yt-dlp and restores full download speeds.

### "Merge required but FFmpeg not found"?
`imageio-ffmpeg` auto-downloads pre-built binaries on first use. If it fails, check your internet connection or install FFmpeg manually:
- Windows: `winget install ffmpeg`
- macOS: `brew install ffmpeg`

### "Video unavailable" or HTTP 403 Forbidden?
1. Update yt-dlp to the latest version: `pip install -U yt-dlp`
2. Set **Browser cookies** in Settings to bypass anti-bot challenges.

---

## 🤝 Third-Party Credits & Licenses
This application relies on the following open-source projects, which are subject to their own respective licenses:
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Unlicense) — Core download engine.
- [CustomTkinter](https://github.com/TomsOpts/CustomTkinter) (MIT License) — Graphical UI framework.
- [Pillow](https://github.com/python-pillow/Pillow) (HPND License) — Image display tools.
- [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) (BSD-2-Clause License) — Bundled FFmpeg path helpers.
- [FFmpeg](https://ffmpeg.org/) (LGPL/GPL) — Multimedia processing binaries.

---

## ⚖️ Legal Notice
This project is intended for **personal use only**. Respect YouTube's Terms of Service and copyright regulations. Download files only if you own the copyrights or have permission from the content owners.

