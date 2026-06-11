"""
ui/tab_downloader.py — Enhanced Downloader Tab
================================================
• Fixed options passed to build_ydl_opts
• Playlist mode: shows video count + first 5 titles after fetch
• Cleaner card layout
• Proper PlaylistJob creation and dispatch
"""

import threading
import uuid
import io
import customtkinter as ctk
from tkinter import filedialog
from PIL import Image
import requests

import downloader as dl
from downloader import (
    QUALITY_MAP, FORMAT_EXT_MAP, AUDIO_FORMATS,
    DownloadItem, PlaylistJob,
    build_ydl_opts, fetch_info,
    get_available_subtitle_langs, get_playlist_entries,
    fmt_duration,
    start_download_thread, start_playlist_thread,
)
from utils.history_manager import add_record

SUBTITLE_COMMON_LANGS = [
    "en", "es", "fr", "de", "it", "pt", "ru", "zh-Hans",
    "zh-Hant", "ja", "ko", "ar", "hi", "tr", "pl", "nl",
    "sv", "da", "fi", "no",
]

_CARD = "#111625"
_BORDER = "#1e293b"
_ACCENT = "#3b82f6"


class DownloaderTab(ctk.CTkFrame):
    def __init__(self, parent, settings: dict, queue_tab=None, history_tab=None):
        super().__init__(parent, fg_color="transparent")
        self.settings    = settings
        self.queue_tab   = queue_tab
        self.history_tab = history_tab
        self._info: dict = {}
        self._fetching   = False
        self._thumb_img  = None
        self._build()

    # ──────────────────────────────────────────────────────────────────
    def _build(self):
        # ── URL card ─────────────────────────────────────────────────
        url_card = ctk.CTkFrame(self, fg_color=_CARD, corner_radius=12,
                                 border_width=1, border_color=_BORDER)
        url_card.pack(fill="x", padx=20, pady=(12, 8))

        ctk.CTkLabel(url_card, text="🔗  YouTube Video / Playlist URL",
                     font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                     text_color="#93c5fd").pack(anchor="w", padx=16, pady=(12, 0))

        url_row = ctk.CTkFrame(url_card, fg_color="transparent")
        url_row.pack(fill="x", padx=16, pady=(6, 12))

        self._url_entry = ctk.CTkEntry(
            url_row,
            placeholder_text="Paste a YouTube video or playlist URL and press Enter…",
            height=42, font=ctk.CTkFont(family="Segoe UI", size=13),
            border_color="#1e293b", fg_color="#0d111d",
            text_color="#f8fafc", placeholder_text_color="#475569"
        )
        self._url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._url_entry.bind("<Return>", lambda _: self._fetch_info())

        ctk.CTkButton(
            url_row, text="📋", width=42, height=42,
            fg_color="#1e293b", hover_color="#334155",
            font=ctk.CTkFont(size=14),
            command=self._paste_url,
        ).pack(side="left", padx=(0, 6))

        self._fetch_btn = ctk.CTkButton(
            url_row, text="🔍  Fetch Info", width=130, height=42,
            fg_color=_ACCENT, hover_color="#2563eb",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._fetch_info,
        )
        self._fetch_btn.pack(side="left")

        # ── Info card ────────────────────────────────────────────────
        self._info_card = ctk.CTkFrame(self, fg_color=_CARD, corner_radius=12,
                                        border_width=1, border_color=_BORDER)
        self._info_card.pack(fill="x", padx=20, pady=(0, 8))
        self._build_info_card()

        # ── Options card ─────────────────────────────────────────────
        opts_card = ctk.CTkFrame(self, fg_color=_CARD, corner_radius=12,
                                  border_width=1, border_color=_BORDER)
        opts_card.pack(fill="x", padx=20, pady=(0, 8))
        self._build_options(opts_card)

        # ── Output row ───────────────────────────────────────────────
        out_card = ctk.CTkFrame(self, fg_color=_CARD, corner_radius=12,
                                 border_width=1, border_color=_BORDER)
        out_card.pack(fill="x", padx=20, pady=(0, 8))

        out_row = ctk.CTkFrame(out_card, fg_color="transparent")
        out_row.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(out_row, text="📂  Save to:",
                     font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                     text_color="#93c5fd").pack(side="left", padx=(0, 10))

        self._out_var = ctk.StringVar(value=self.settings.get("output_dir", ""))
        ctk.CTkEntry(out_row, textvariable=self._out_var,
                     height=36, fg_color="#0d111d",
                     border_color="#1e293b", text_color="#f8fafc").pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(out_row, text="Browse", width=80, height=36,
                      fg_color="#1e293b", hover_color="#334155",
                      font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                      command=self._browse_output).pack(side="left")

        # ── Download button ──────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 12))

        self._dl_btn = ctk.CTkButton(
            btn_frame, text="⬇   Download Now", height=52,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            fg_color="#10b981", hover_color="#059669",  # Emerald green Accent
            command=self._start_download,
        )
        self._dl_btn.pack(fill="x")

        self._msg_lbl = ctk.CTkLabel(
            btn_frame, text="",
            text_color="#94a3b8", font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self._msg_lbl.pack(pady=(4, 0))

    # ──────────────────────────────────────────────────────────────────
    def _build_info_card(self):
        inner = ctk.CTkFrame(self._info_card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)

        # Thumbnail
        self._thumb_lbl = ctk.CTkLabel(
            inner, text="No video loaded\nFetch a URL to view details",
            width=180, height=101,
            fg_color="#0d111d", corner_radius=8,
            text_color="#475569", font=ctk.CTkFont(family="Segoe UI", size=10),
        )
        self._thumb_lbl.pack(side="left", padx=(0, 16))

        # Metadata column
        meta = ctk.CTkFrame(inner, fg_color="transparent")
        meta.pack(side="left", fill="both", expand=True)

        self._title_lbl = ctk.CTkLabel(
            meta,
            text="Paste a YouTube URL and click 'Fetch Info' to parse metadata",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            wraplength=500, justify="left", anchor="nw",
            text_color="#94a3b8",
        )
        self._title_lbl.pack(anchor="w")

        stats = ctk.CTkFrame(meta, fg_color="transparent")
        stats.pack(anchor="w", pady=(8, 0))

        # Pill Badges for metadata
        self._ch_lbl   = ctk.CTkLabel(stats, text="", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), fg_color="transparent", corner_radius=6)
        self._dur_lbl  = ctk.CTkLabel(stats, text="", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), fg_color="transparent", corner_radius=6)
        self._view_lbl = ctk.CTkLabel(stats, text="", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), fg_color="transparent", corner_radius=6)
        self._type_lbl = ctk.CTkLabel(stats, text="", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), fg_color="transparent", corner_radius=6)
        self._ch_lbl.pack(side="left", padx=(0, 10))
        self._dur_lbl.pack(side="left", padx=(0, 10))
        self._view_lbl.pack(side="left", padx=(0, 10))
        self._type_lbl.pack(side="left")

        # Playlist preview (hidden until playlist detected)
        self._playlist_frame = ctk.CTkFrame(meta, fg_color="#0d111d",
                                             corner_radius=6, border_width=1, border_color="#1e293b")
        self._playlist_lbl = ctk.CTkLabel(
            self._playlist_frame, text="",
            font=ctk.CTkFont(family="Consolas", size=10), text_color="#94a3b8",
            justify="left", anchor="w", wraplength=480,
        )
        self._playlist_lbl.pack(anchor="w", padx=10, pady=8)

        # Subtitle row
        sub_row = ctk.CTkFrame(meta, fg_color="transparent")
        sub_row.pack(anchor="w", pady=(12, 0))

        self._sub_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            sub_row, text="Download Subtitles",
            variable=self._sub_var,
            fg_color=_ACCENT, hover_color="#2563eb",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        ).pack(side="left", padx=(0, 12))

        self._sub_lang_var = ctk.StringVar(value=self.settings.get("subtitle_lang", "en"))
        ctk.CTkOptionMenu(
            sub_row, variable=self._sub_lang_var,
            values=SUBTITLE_COMMON_LANGS, width=90,
            fg_color="#1e293b", button_color="#1e293b", button_hover_color="#334155",
            dropdown_fg_color="#0f172a", dropdown_hover_color="#1e293b",
            text_color="#f8fafc", font=ctk.CTkFont(family="Segoe UI", size=11)
        ).pack(side="left", padx=(0, 8))

        self._embed_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(sub_row, text="Embed in file",
                        variable=self._embed_var,
                        fg_color=_ACCENT, hover_color="#2563eb",
                        font=ctk.CTkFont(family="Segoe UI", size=11)).pack(side="left", padx=(0, 8))

        self._autosub_var = ctk.BooleanVar(value=self.settings.get("auto_subtitles", True))
        ctk.CTkCheckBox(sub_row, text="Auto-captions",
                        variable=self._autosub_var,
                        fg_color=_ACCENT, hover_color="#2563eb",
                        font=ctk.CTkFont(family="Segoe UI", size=11)).pack(side="left")

    def _build_options(self, parent):
        ctk.CTkLabel(parent, text="⚙  Format & Quality Options",
                     font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                     text_color="#93c5fd").pack(anchor="w", padx=16, pady=(12, 4))

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 12))

        def _col(label, widget_fn):
            col = ctk.CTkFrame(row, fg_color="transparent")
            col.pack(side="left", padx=(0, 20))
            ctk.CTkLabel(col, text=label, font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                         text_color="#64748b").pack(anchor="w")
            widget_fn(col).pack(anchor="w", pady=(2, 0))
            return col

        dropdown_styles = {
            "fg_color": "#1e293b",
            "button_color": "#1e293b",
            "button_hover_color": "#334155",
            "dropdown_fg_color": "#0f172a",
            "dropdown_hover_color": "#1e293b",
            "text_color": "#f8fafc",
            "font": ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        }

        self._qual_var = ctk.StringVar(value=self.settings.get("default_quality", "1080p"))
        _col("Quality Target", lambda p: ctk.CTkOptionMenu(
            p, variable=self._qual_var,
            values=list(QUALITY_MAP.keys()), width=110,
            **dropdown_styles
        ))

        self._fmt_var = ctk.StringVar(value=self.settings.get("default_format", "mp4"))
        _col("Format Ext", lambda p: ctk.CTkOptionMenu(
            p, variable=self._fmt_var,
            values=list(FORMAT_EXT_MAP.keys()), width=90,
            command=self._on_format_change,
            **dropdown_styles
        ))

        self._codec_var = ctk.StringVar(value=self.settings.get("default_codec", "h264"))
        self._codec_col = _col("Video Codec", lambda p: ctk.CTkOptionMenu(
            p, variable=self._codec_var,
            values=["h264", "h265", "vp9", "av1"], width=90,
            **dropdown_styles
        ))

        self._aq_var = ctk.StringVar(value="Best")
        _col("Audio Bitrate", lambda p: ctk.CTkOptionMenu(
            p, variable=self._aq_var,
            values=["Best", "320kbps", "256kbps", "192kbps", "128kbps", "64kbps"],
            width=110,
            **dropdown_styles
        ))

        # Playlist toggle
        pl_col = ctk.CTkFrame(row, fg_color="transparent")
        pl_col.pack(side="left")
        ctk.CTkLabel(pl_col, text="Playlist Mode",
                     font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"), text_color="#64748b").pack(anchor="w")
        self._playlist_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(pl_col, text="", variable=self._playlist_var,
                      progress_color=_ACCENT, width=46).pack(anchor="w", pady=(2, 0))

    # ──────────────────────────────────────────────────────────────────
    def _on_format_change(self, value):
        state = "disabled" if value in AUDIO_FORMATS else "normal"
        for w in self._codec_col.winfo_children():
            try:
                w.configure(state=state)
            except Exception:
                pass

    def _paste_url(self):
        try:
            txt = self.clipboard_get()
            self._url_entry.delete(0, "end")
            self._url_entry.insert(0, txt.strip())
        except Exception:
            pass

    def _browse_output(self):
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            self._out_var.set(d)
            self.settings["output_dir"] = d

    # ──────────────────────────────────────────────────────────────────
    def _fetch_info(self):
        url = self._url_entry.get().strip()
        if not url:
            self._set_msg("⚠  Please enter a URL first.", "#fbbf24")
            return
        if self._fetching:
            return
        self._fetching = True
        self._fetch_btn.configure(text="⏳  Fetching…", state="disabled")
        self._set_msg("Fetching video information…", "#7dd3fc")

        def _work():
            try:
                info = fetch_info(
                    url,
                    ffmpeg_path=self.settings.get("ffmpeg_path", ""),
                    cookies_browser=self.settings.get("cookies_browser", ""),
                    proxy=self.settings.get("proxy", ""),
                )
                self.after(0, lambda: self._on_info_loaded(info))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._on_info_error(err))

        threading.Thread(target=_work, daemon=True).start()

    def _on_info_loaded(self, info: dict):
        self._info = info
        self._fetching = False
        self._fetch_btn.configure(text="🔍  Fetch Info", state="normal")

        title    = info.get("title", "Unknown title")
        uploader = info.get("uploader") or info.get("channel", "Unknown")
        duration = fmt_duration(info.get("duration"))
        views    = info.get("view_count")
        is_playlist = bool(info.get("entries"))

        self._title_lbl.configure(text=title[:120], text_color="#f8fafc")

        # Configure Channel badge
        self._ch_lbl.configure(text=f" 👤  {uploader[:30]} ", fg_color="#1e293b", text_color="#94a3b8")

        if not is_playlist:
            # Configure Duration badge
            self._dur_lbl.configure(text=f" ⏱  {duration} ", fg_color="#112a1d", text_color="#34d399")
            self._dur_lbl.pack(side="left", padx=(0, 10))

            # Configure Views badge
            if views:
                self._view_lbl.configure(text=f" 👁  {views:,} ", fg_color="#2d161a", text_color="#f43f5e")
                self._view_lbl.pack(side="left", padx=(0, 10))
            else:
                self._view_lbl.pack_forget()

            # Configure Type badge
            self._type_lbl.configure(text=" 🎬  Video ", fg_color="#2e1b0d", text_color="#fbbf24")

            self._playlist_frame.pack_forget()
            self._playlist_var.set(False)
        else:
            # Playlists don't have duration / views directly in header
            self._dur_lbl.pack_forget()
            self._view_lbl.pack_forget()

            entries = get_playlist_entries(info)
            count   = len(entries)

            # Configure Type badge
            self._type_lbl.configure(text=f" 📋  Playlist ({count} items) ", fg_color="#1d1b4b", text_color="#818cf8")

            preview = "\n".join(
                f"  {i+1}. {e['title'][:60]}" for i, e in enumerate(entries[:6])
            )
            if count > 6:
                preview += f"\n  … and {count - 6} more"
            self._playlist_lbl.configure(text=preview)
            self._playlist_frame.pack(anchor="w", pady=(10, 0), fill="x")

            # Auto-enable playlist mode
            self._playlist_var.set(True)

        self._set_msg(f"✅  Loaded: {title[:55]}", "#10b981")

        # Fetch thumbnail
        thumb_url = info.get("thumbnail") or ""
        if thumb_url:
            threading.Thread(
                target=self._load_thumbnail, args=(thumb_url,), daemon=True
            ).start()

    def _on_info_error(self, err: str):
        self._fetching = False
        self._fetch_btn.configure(text="🔍  Fetch Info", state="normal")
        self._set_msg(f"❌  {err[:120]}", "#f87171")

    def _load_thumbnail(self, url: str):
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content))
            img.thumbnail((180, 101))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(180, 101))
            self.after(0, lambda: self._thumb_lbl.configure(image=ctk_img, text=""))
            self._thumb_img = ctk_img
        except Exception:
            pass

    def _start_download(self):
        url = self._url_entry.get().strip()
        if not url:
            self._set_msg("⚠  Please enter a URL first.", "#fbbf24")
            return

        if self.queue_tab and self.queue_tab.has_url(url):
            self._set_msg("⚠  This URL is already in the active download queue.", "#fbbf24")
            return

        output_dir = self._out_var.get().strip()
        if not output_dir:
            self._set_msg("⚠  Please select an output folder.", "#fbbf24")
            return

        sub_enabled = self._sub_var.get()
        sub_langs   = [self._sub_lang_var.get()] if sub_enabled else []

        quality = self._qual_var.get()
        fmt     = self._fmt_var.get()

        opts = build_ydl_opts(
            output_dir          = output_dir,
            quality             = quality,
            fmt                 = fmt,
            codec               = self._codec_var.get(),
            audio_quality       = self._aq_var.get(),
            subtitle_langs      = sub_langs,
            embed_subs          = self._embed_var.get() if sub_enabled else False,
            write_subs          = sub_enabled,
            auto_subs           = self._autosub_var.get() if sub_enabled else False,
            proxy               = self.settings.get("proxy", ""),
            rate_limit          = self.settings.get("rate_limit", ""),
            ffmpeg_path         = self.settings.get("ffmpeg_path", ""),
            organize_by_channel = self.settings.get("organize_by_channel", False),
            avoid_duplicates    = self.settings.get("avoid_duplicates", True),
            filename_template   = self.settings.get("filename_template", "%(title)s.%(ext)s"),
            playlist            = self._playlist_var.get(),
            cookies_browser     = self.settings.get("cookies_browser", ""),
        )
        # Stash for history record
        opts["_output_dir"] = output_dir
        opts["_quality"]    = quality
        opts["_fmt"]        = fmt

        item_id  = str(uuid.uuid4())[:8]
        is_pl    = self._playlist_var.get()
        info_title = self._info.get("title", url) if self._info else url

        if is_pl and self._info and self._info.get("entries"):
            # ── Playlist job ─────────────────────────────────────────
            job = PlaylistJob(url, opts, item_id)
            job.title = info_title

            if self.queue_tab:
                self.queue_tab.add_playlist(job, on_cancel=lambda _: None)

            start_playlist_thread(
                job,
                on_progress=lambda j: self.after(0, lambda: self.queue_tab and self.queue_tab.update_playlist(j)),
                on_complete=lambda j: self.after(0, lambda: self._on_playlist_done(j)),
            )
            self._set_msg(f"✅  Playlist queued: {info_title[:50]}", "#4ade80")

        else:
            # ── Single video ─────────────────────────────────────────
            item = DownloadItem(url, opts, item_id)
            item.title    = info_title
            item._quality = quality
            item._fmt     = fmt

            if self.queue_tab:
                self.queue_tab.add_item(item, on_cancel=lambda _: None)

            start_download_thread(
                item,
                on_progress=lambda it: self.after(0, lambda: self.queue_tab and self.queue_tab.update_item(it)),
                on_complete=lambda it: self.after(0, lambda: self._on_item_done(it)),
            )
            self._set_msg(f"✅  Added to queue: {info_title[:50]}", "#4ade80")

    def _on_item_done(self, item: DownloadItem):
        if self.queue_tab:
            self.queue_tab.update_item(item)
        if item.status == DownloadItem.STATUS_DONE:
            add_record({
                "title":    item.title,
                "url":      item.url,
                "filepath": item.filepath,
                "quality":  getattr(item, "_quality", ""),
                "fmt":      getattr(item, "_fmt", ""),
                "size_bytes": None,
            })
            if self.history_tab:
                self.after(500, self.history_tab.refresh)

    def _on_playlist_done(self, job: PlaylistJob):
        if self.queue_tab:
            self.queue_tab.update_playlist(job)
        if self.history_tab:
            self.after(500, self.history_tab.refresh)

    def _set_msg(self, text: str, color: str = "#94a3b8"):
        self._msg_lbl.configure(text=text, text_color=color)
