"""
ui/tab_history.py
Download history panel — shows past completed downloads with real-time search, file verification, and play actions.
"""

import os
import subprocess
from datetime import datetime
import customtkinter as ctk
from utils.history_manager import load_history, clear_history
from downloader import fmt_size, fmt_duration


class HistoryTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._rows: list[ctk.CTkFrame] = []
        self._build()

    def _build(self):
        # Top bar
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(
            top, text="📋  Download History",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#f8fafc"
        ).pack(side="left")

        # Search Bar
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *args: self.refresh())
        self._search_entry = ctk.CTkEntry(
            top, textvariable=self._search_var,
            placeholder_text="🔍  Search by title, quality, format...",
            width=280, height=32,
            border_color="#1e293b", fg_color="#0d111d",
            text_color="#f8fafc", placeholder_text_color="#475569"
        )
        self._search_entry.pack(side="left", padx=20)

        # Clear & Refresh Buttons
        ctk.CTkButton(
            top, text="🗑  Clear History", width=130, height=32,
            fg_color="#331c1e", hover_color="#7f1d1d",
            text_color="#f87171",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._clear
        ).pack(side="right")

        ctk.CTkButton(
            top, text="⟳  Refresh", width=90, height=32,
            fg_color="#1e293b", hover_color="#334155",
            text_color="#94a3b8",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.refresh
        ).pack(side="right", padx=(0, 8))

        # Column headers table frame
        hdr = ctk.CTkFrame(self, fg_color="#111625", corner_radius=6, border_width=1, border_color="#1e293b")
        hdr.pack(fill="x", padx=16, pady=(12, 0))
        for text, w in [("Title", 310), ("Quality", 80), ("Format", 70),
                        ("Size", 80), ("Completed Date", 140), ("Actions", 130)]:
            ctk.CTkLabel(hdr, text=text, width=w, anchor="w",
                         font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                         text_color="#64748b").pack(side="left", padx=6, pady=8)

        # Scrollable list
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=16, pady=8)

        self.refresh()

    def refresh(self):
        # Clear existing rows
        for widget in self.scroll.winfo_children():
            widget.destroy()

        history = load_history()
        if not history:
            ctk.CTkLabel(
                self.scroll,
                text="No downloads found in history.",
                text_color="#475569",
                font=ctk.CTkFont(family="Segoe UI", size=13),
            ).pack(pady=60)
            return

        search_query = self._search_var.get().strip().lower()
        filtered_history = []
        for record in history:
            title = record.get("title", "").lower()
            fmt = record.get("fmt", "").lower()
            quality = record.get("quality", "").lower()
            if not search_query or search_query in title or search_query in fmt or search_query in quality:
                filtered_history.append(record)

        if not filtered_history:
            ctk.CTkLabel(
                self.scroll,
                text="No search matches found.",
                text_color="#475569",
                font=ctk.CTkFont(family="Segoe UI", size=13),
            ).pack(pady=40)
            return

        for record in filtered_history:
            self._add_row(record)

    def _add_row(self, record: dict):
        row = ctk.CTkFrame(self.scroll, fg_color="#111625", corner_radius=10, border_width=1, border_color="#1e293b")
        row.pack(fill="x", pady=4)

        title = record.get("title", "Unknown")[:50]
        quality = record.get("quality", "—")
        fmt = record.get("fmt", "—")
        size = fmt_size(record.get("size_bytes"))
        filepath = record.get("filepath", "")

        raw_date = record.get("date", "")
        try:
            dt = datetime.fromisoformat(raw_date)
            date_str = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            date_str = raw_date[:16] if raw_date else "—"

        # Content fields
        ctk.CTkLabel(row, text=title, width=310, anchor="w",
                     text_color="#f8fafc",
                     font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")).pack(side="left", padx=6)
        ctk.CTkLabel(row, text=quality, width=80, anchor="w",
                     font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                     text_color="#60a5fa").pack(side="left")
        ctk.CTkLabel(row, text=fmt.upper(), width=70, anchor="w",
                     font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                     text_color="#34d399").pack(side="left")
        ctk.CTkLabel(row, text=size, width=80, anchor="w",
                     font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                     text_color="#fb7185").pack(side="left")
        ctk.CTkLabel(row, text=date_str, width=140, anchor="w",
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color="#475569").pack(side="left")

        # Action Buttons frame
        btn_frame = ctk.CTkFrame(row, fg_color="transparent")
        btn_frame.pack(side="left", padx=4, fill="y")

        file_exists = os.path.exists(filepath) if filepath else False

        # Folder containing file
        ctk.CTkButton(
            btn_frame, text="📂 Folder", width=62, height=24,
            fg_color="#1e293b", hover_color="#334155",
            text_color="#94a3b8",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            command=lambda p=filepath: self._open_folder(p),
        ).pack(side="left", padx=2, pady=6)

        # Direct Play or Lost indicator
        if file_exists:
            ctk.CTkButton(
                btn_frame, text="▶ Play", width=54, height=24,
                fg_color="#10b981", hover_color="#059669",
                text_color="#ffffff",
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                command=lambda p=filepath: self._play_file(p),
            ).pack(side="left", padx=2, pady=6)
        else:
            ctk.CTkButton(
                btn_frame, text="⚠ Lost", width=54, height=24,
                fg_color="#271b1c", hover_color="#271b1c",
                text_color="#f43f5e",
                state="disabled",
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            ).pack(side="left", padx=2, pady=6)

    def _open_folder(self, filepath: str):
        if not filepath:
            return
        folder = os.path.dirname(filepath)
        if not os.path.exists(folder):
            folder = os.path.expanduser("~")
        try:
            if os.name == "nt":
                if os.path.exists(filepath):
                    subprocess.Popen(["explorer", "/select,", filepath])
                else:
                    os.startfile(folder)
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            print(f"[History] Could not open folder: {e}")

    def _play_file(self, filepath: str):
        if not filepath or not os.path.exists(filepath):
            return
        try:
            if os.name == "nt":
                os.startfile(filepath)
            else:
                subprocess.Popen(["xdg-open", filepath])
        except Exception as e:
            print(f"[History] Could not play file: {e}")

    def _clear(self):
        clear_history()
        self.refresh()
