"""
ui/tab_queue.py
Enhanced download queue with:
  - Internet-lost warning banner (auto-shown/hidden)
  - Playlist rows with overall + per-video progress
  - Better card design and status colours
"""

import customtkinter as ctk
from downloader import DownloadItem, PlaylistJob


# Status → (background, foreground) theme colors
_STATUS_THEME = {
    DownloadItem.STATUS_QUEUED:      ("#1e293b", "#94a3b8"), # Slate
    DownloadItem.STATUS_FETCHING:    ("#2e1b0d", "#fbbf24"), # Amber
    DownloadItem.STATUS_DOWNLOADING: ("#0c2340", "#38bdf8"), # Blue
    DownloadItem.STATUS_MERGING:     ("#23153c", "#a78bfa"), # Purple
    DownloadItem.STATUS_CONVERTING:  ("#23153c", "#a78bfa"), # Purple
    DownloadItem.STATUS_NO_INTERNET: ("#331800", "#fb923c"), # Orange/Amber
    DownloadItem.STATUS_RESUMING:    ("#062f22", "#34d399"), # Emerald
    DownloadItem.STATUS_DONE:        ("#062f22", "#4ade80"), # Green
    DownloadItem.STATUS_ERROR:       ("#2d1215", "#f87171"), # Red
    DownloadItem.STATUS_CANCELLED:   ("#1c1c1c", "#94a3b8"), # Gray
}


class QueueTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._item_frames: dict[str, "_ItemRow | _PlaylistRow"] = {}
        self._build()

    def _build(self):
        # ── Top bar ──────────────────────────────────────────────────
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 4))

        ctk.CTkLabel(top, text="📥  Active Download Queue",
                     font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
                     text_color="#f8fafc").pack(side="left")

        self._status_lbl = ctk.CTkLabel(top, text="",
                                         text_color="#64748b",
                                         font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"))
        self._status_lbl.pack(side="right")

        # ── Internet-lost banner (hidden by default) ─────────────────
        self._banner = ctk.CTkFrame(self, fg_color="#27110a",
                                     corner_radius=10, border_width=1, border_color="#7c2d12")
        # Banner content
        _b_inner = ctk.CTkFrame(self._banner, fg_color="transparent")
        _b_inner.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(
            _b_inner,
            text="⚡  No Internet Connection Detected",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#fef3c7",
        ).pack(anchor="w")
        ctk.CTkLabel(
            _b_inner,
            text="Downloads are paused and will resume automatically when your connection is restored. Partial file fragments are preserved.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#fde68a",
            wraplength=620,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

        # ── Scrollable list ──────────────────────────────────────────
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=16, pady=8)

        self._empty_lbl = ctk.CTkLabel(
            self.scroll,
            text="No active downloads in queue.\nPaste a URL on the Downloader tab to start downloading.",
            text_color="#475569",
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self._empty_lbl.pack(pady=80)

    # ── Connectivity banner ──────────────────────────────────────────
    def show_no_internet(self):
        self._banner.pack(fill="x", padx=16, pady=(0, 6))
        # Safely ensure scroll is packed after the banner without using before=
        if self.scroll.winfo_manager() == "pack":
            self.scroll.pack_forget()
        self.scroll.pack(fill="both", expand=True, padx=16, pady=8)

    def hide_no_internet(self):
        self._banner.pack_forget()

    # ── Item management ──────────────────────────────────────────────
    def add_item(self, item: DownloadItem, on_cancel: callable):
        self._empty_lbl.pack_forget()
        row = _ItemRow(self.scroll, item, on_cancel)
        row.pack(fill="x", pady=6)
        self._item_frames[item.item_id] = row
        self._update_status()

    def add_playlist(self, job: PlaylistJob, on_cancel: callable):
        self._empty_lbl.pack_forget()
        row = _PlaylistRow(self.scroll, job, on_cancel)
        row.pack(fill="x", pady=6)
        self._item_frames[job.item_id] = row
        self._update_status()

    def update_item(self, item: DownloadItem):
        row = self._item_frames.get(item.item_id)
        if isinstance(row, _ItemRow):
            row.refresh(item)
        self._update_status()

    def update_playlist(self, job: PlaylistJob):
        row = self._item_frames.get(job.item_id)
        if isinstance(row, _PlaylistRow):
            row.refresh(job)
        self._update_status()

    def remove_item(self, item_id: str):
        row = self._item_frames.pop(item_id, None)
        if row:
            row.destroy()
        if not self._item_frames:
            self._empty_lbl.pack(pady=80)
        self._update_status()

    def _update_status(self):
        active = sum(
            1 for r in self._item_frames.values()
            if getattr(r, "_status_text", "") in (
                DownloadItem.STATUS_DOWNLOADING,
                DownloadItem.STATUS_MERGING,
                PlaylistJob.STATUS_DOWNLOADING,
            )
        )
        total = len(self._item_frames)
        self._status_lbl.configure(
            text=f"{active} active · {total} total" if total else ""
        )

    def has_url(self, url: str) -> bool:
        """Check if URL is currently in the active queue."""
        for row in self._item_frames.values():
            if hasattr(row, "_item") and row._item.url == url:
                if row._item.status not in (DownloadItem.STATUS_DONE, DownloadItem.STATUS_CANCELLED, DownloadItem.STATUS_ERROR):
                    return True
            if hasattr(row, "_job") and row._job.url == url:
                if row._job.status not in (PlaylistJob.STATUS_DONE, PlaylistJob.STATUS_CANCELLED, PlaylistJob.STATUS_ERROR):
                    return True
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Single video row
# ─────────────────────────────────────────────────────────────────────────────
class _ItemRow(ctk.CTkFrame):
    def __init__(self, parent, item: DownloadItem, on_cancel: callable):
        super().__init__(parent, fg_color="#111625",
                         corner_radius=12,
                         border_width=1, border_color="#1e293b")
        self._item = item
        self._on_cancel = on_cancel
        self._status_text = item.status
        self._build()

    def _build(self):
        # Row 1: title + badge + cancel
        r1 = ctk.CTkFrame(self, fg_color="transparent")
        r1.pack(fill="x", padx=14, pady=(12, 6))

        self._title_lbl = ctk.CTkLabel(
            r1, text=self._item.title[:72],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#f8fafc",
            anchor="w",
        )
        self._title_lbl.pack(side="left", fill="x", expand=True)

        bg, fg = _STATUS_THEME.get(self._item.status, ("#1e293b", "#94a3b8"))
        self._badge = ctk.CTkLabel(
            r1, text=f"  {self._item.status.upper()}  ",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=fg, fg_color=bg, corner_radius=6,
            height=20
        )
        self._badge.pack(side="left", padx=8)

        self._cancel_btn = ctk.CTkButton(
            r1, text="✕", width=28, height=28,
            fg_color="#332a2c", hover_color="#7f1d1d",
            font=ctk.CTkFont(size=11),
            text_color="#f87171",
            corner_radius=6,
            command=self._cancel,
        )
        self._cancel_btn.pack(side="left")

        # Progress bar
        self._bar = ctk.CTkProgressBar(self, height=6, corner_radius=3,
                                        progress_color="#3b82f6")
        self._bar.set(0)
        self._bar.pack(fill="x", padx=14, pady=(0, 6))

        # Row 2: stats
        r2 = ctk.CTkFrame(self, fg_color="transparent")
        r2.pack(fill="x", padx=14, pady=(0, 10))

        self._pct_lbl   = ctk.CTkLabel(r2, text="0%",   width=42, anchor="w",
                                        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                                        text_color="#3b82f6")
        self._speed_lbl = ctk.CTkLabel(r2, text="",     width=95, anchor="w",
                                        font=ctk.CTkFont(family="Segoe UI", size=10),
                                        text_color="#10b981")
        self._eta_lbl   = ctk.CTkLabel(r2, text="",     width=85, anchor="w",
                                        font=ctk.CTkFont(family="Segoe UI", size=10),
                                        text_color="#fbbf24")
        self._url_lbl   = ctk.CTkLabel(r2, text=self._item.url[:65],
                                        font=ctk.CTkFont(family="Consolas", size=9),
                                        text_color="#475569", anchor="w")
        self._pct_lbl.pack(side="left")
        self._speed_lbl.pack(side="left")
        self._eta_lbl.pack(side="left")
        self._url_lbl.pack(side="left", padx=(6, 0))

    def refresh(self, item: DownloadItem):
        self._item = item
        self._status_text = item.status
        bg, fg = _STATUS_THEME.get(item.status, ("#1e293b", "#94a3b8"))

        self._title_lbl.configure(text=item.title[:72])
        self._badge.configure(text=f"  {item.status.upper()}  ", text_color=fg, fg_color=bg)
        self._bar.set(max(0, min(1, item.percent / 100)))
        self._pct_lbl.configure(text=f"{item.percent:.0f}%")
        self._speed_lbl.configure(text=item.speed or "")
        self._eta_lbl.configure(text=f"ETA {item.eta}" if item.eta and item.eta != "—" else "")

        if item.status == DownloadItem.STATUS_ERROR:
            self._url_lbl.configure(text=f"Error: {item.error}", text_color="#f43f5e")
        else:
            self._url_lbl.configure(text=item.url[:65], text_color="#475569")

        # Progress bar color custom mapping
        bar_colors = {
            DownloadItem.STATUS_DONE:        "#10b981",
            DownloadItem.STATUS_ERROR:       "#f43f5e",
            DownloadItem.STATUS_MERGING:     "#818cf8",
            DownloadItem.STATUS_NO_INTERNET: "#fb923c",
            DownloadItem.STATUS_RESUMING:    "#10b981",
            DownloadItem.STATUS_CANCELLED:   "#475569",
        }
        self._bar.configure(
            progress_color=bar_colors.get(item.status, "#3b82f6")
        )

        done = item.status in (
            DownloadItem.STATUS_DONE,
            DownloadItem.STATUS_CANCELLED,
            DownloadItem.STATUS_ERROR,
        )
        if done:
            self._cancel_btn.configure(state="disabled", fg_color="#1e293b", text_color="#475569")

    def _cancel(self):
        self._item.cancel()


# ─────────────────────────────────────────────────────────────────────────────
# Playlist job row
# ─────────────────────────────────────────────────────────────────────────────
class _PlaylistRow(ctk.CTkFrame):
    def __init__(self, parent, job: PlaylistJob, on_cancel: callable):
        super().__init__(parent, fg_color="#111625",
                         corner_radius=12,
                         border_width=1, border_color="#1e293b")
        self._job = job
        self._on_cancel = on_cancel
        self._status_text = job.status
        self._build()

    def _build(self):
        # Header row
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(12, 6))

        ctk.CTkLabel(hdr, text="📋",
                     font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 6))

        self._title_lbl = ctk.CTkLabel(
            hdr, text=self._job.title[:65],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#f8fafc", anchor="w",
        )
        self._title_lbl.pack(side="left", fill="x", expand=True)

        self._count_lbl = ctk.CTkLabel(
            hdr, text="", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#60a5fa", width=100, anchor="e",
        )
        self._count_lbl.pack(side="left", padx=6)

        bg, fg = _STATUS_THEME.get(self._job.status, ("#1e293b", "#94a3b8"))
        self._badge = ctk.CTkLabel(
            hdr, text=f"  {self._job.status.upper()}  ",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=fg, fg_color=bg, corner_radius=6,
            height=20
        )
        self._badge.pack(side="left", padx=4)

        self._cancel_btn = ctk.CTkButton(
            hdr, text="✕", width=28, height=28,
            fg_color="#332a2c", hover_color="#7f1d1d",
            font=ctk.CTkFont(size=11),
            text_color="#f87171",
            corner_radius=6,
            command=self._cancel,
        )
        self._cancel_btn.pack(side="left")

        # Overall progress bar
        overall_lbl = ctk.CTkFrame(self, fg_color="transparent")
        overall_lbl.pack(fill="x", padx=14)
        ctk.CTkLabel(overall_lbl, text="OVERALL PLAYLIST PROGRESS", font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                     text_color="#475569").pack(side="left")

        self._overall_bar = ctk.CTkProgressBar(self, height=6,
                                                corner_radius=3,
                                                progress_color="#6366f1")
        self._overall_bar.set(0)
        self._overall_bar.pack(fill="x", padx=14, pady=(2, 8))

        # Divider
        ctk.CTkFrame(self, height=1, fg_color="#1e293b").pack(fill="x", padx=14)

        # Current video sub-row
        sub = ctk.CTkFrame(self, fg_color="#0d111d", corner_radius=8, border_width=1, border_color="#1e293b")
        sub.pack(fill="x", padx=14, pady=(8, 10))

        r1 = ctk.CTkFrame(sub, fg_color="transparent")
        r1.pack(fill="x", padx=10, pady=(6, 4))

        ctk.CTkLabel(r1, text="▶", font=ctk.CTkFont(size=10),
                     text_color="#38bdf8").pack(side="left", padx=(0, 6))

        self._cur_title = ctk.CTkLabel(
            r1, text="Waiting in queue…",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), anchor="w",
            text_color="#cbd5e1",
        )
        self._cur_title.pack(side="left", fill="x", expand=True)

        r2 = ctk.CTkFrame(sub, fg_color="transparent")
        r2.pack(fill="x", padx=10)

        self._cur_bar = ctk.CTkProgressBar(r2, height=4, corner_radius=2,
                                            progress_color="#3b82f6")
        self._cur_bar.set(0)
        self._cur_bar.pack(fill="x", pady=(0, 4))

        r3 = ctk.CTkFrame(sub, fg_color="transparent")
        r3.pack(fill="x", padx=10, pady=(0, 6))

        self._cur_pct   = ctk.CTkLabel(r3, text="0%",  width=40, anchor="w",
                                        font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                                        text_color="#3b82f6")
        self._cur_speed = ctk.CTkLabel(r3, text="",    width=90, anchor="w",
                                        font=ctk.CTkFont(family="Segoe UI", size=9),
                                        text_color="#10b981")
        self._cur_eta   = ctk.CTkLabel(r3, text="",    width=80, anchor="w",
                                        font=ctk.CTkFont(family="Segoe UI", size=9),
                                        text_color="#fbbf24")
        self._cur_pct.pack(side="left")
        self._cur_speed.pack(side="left")
        self._cur_eta.pack(side="left")

    def refresh(self, job: PlaylistJob):
        self._job = job
        self._status_text = job.status
        bg, fg = _STATUS_THEME.get(job.status, ("#1e293b", "#94a3b8"))

        self._title_lbl.configure(text=job.title[:65])
        self._badge.configure(text=f"  {job.status.upper()}  ", text_color=fg, fg_color=bg)

        if job.total > 0:
            n = job.current_index + 1
            self._count_lbl.configure(text=f"Video {n} of {job.total}")

        self._overall_bar.set(max(0, min(1, job.percent / 100)))

        # Color overall bar
        bar_colors = {
            PlaylistJob.STATUS_DONE:        "#10b981",
            PlaylistJob.STATUS_NO_INTERNET: "#fb923c",
            PlaylistJob.STATUS_ERROR:       "#f43f5e",
        }
        self._overall_bar.configure(
            progress_color=bar_colors.get(job.status, "#6366f1")
        )

        # Current video sub-row
        if job.status == PlaylistJob.STATUS_ERROR:
            self._cur_title.configure(text=f"Error: {getattr(job, 'error', 'Unknown error')}", text_color="#f43f5e")
        else:
            cur_title = job.current_video_title
            if cur_title:
                self._cur_title.configure(text=cur_title[:80], text_color="#cbd5e1")
        self._cur_bar.set(max(0, min(1, job.current_video_percent / 100)))
        self._cur_pct.configure(text=f"{job.current_video_percent:.0f}%")
        spd = job.current_video_speed
        eta = job.current_video_eta
        self._cur_speed.configure(text=spd if spd and spd != "—" else "")
        self._cur_eta.configure(
            text=f"ETA {eta}" if eta and eta not in ("—", "") else ""
        )

        done = job.status in (
            PlaylistJob.STATUS_DONE,
            PlaylistJob.STATUS_CANCELLED,
            PlaylistJob.STATUS_ERROR,
        )
        if done:
            self._cancel_btn.configure(state="disabled", fg_color="#1e293b", text_color="#475569")

    def _cancel(self):
        self._job.cancel()
