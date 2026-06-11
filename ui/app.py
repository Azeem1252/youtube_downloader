"""
ui/app.py — Enhanced main application window
=============================================
• Animated connectivity dot in header (green / amber / red)
• Starts ConnectivityMonitor; registers on_lost / on_restored hooks
• Passes connectivity state to queue tab banner
"""

import customtkinter as ctk
from utils.settings_manager import load_settings, save_settings
from utils.ffmpeg_checker import ffmpeg_status_message
from utils.connectivity import monitor as net_monitor

from ui.tab_downloader import DownloaderTab
from ui.tab_queue      import QueueTab
from ui.tab_history    import HistoryTab
from ui.tab_settings   import SettingsTab

APP_VERSION = "2.1.0"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.settings = load_settings()
        ctk.set_appearance_mode(self.settings.get("theme", "dark"))
        ctk.set_default_color_theme("blue")

        self.title("YT Downloader Pro")
        self.geometry("960x740")
        self.minsize(800, 600)

        self._set_icon()
        self._build()

        # ── Start connectivity monitor ────────────────────────────────
        net_monitor.on_lost(self._on_net_lost)
        net_monitor.on_restored(self._on_net_restored)
        net_monitor.start()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Icon ──────────────────────────────────────────────────────────
    def _set_icon(self):
        import os
        icon_path = os.path.join(
            os.path.dirname(__file__), "..", "assets", "icon.ico"
        )
        try:
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

    # ── Build UI ──────────────────────────────────────────────────────
    def _build(self):
        self.configure(fg_color="#0b0f19")

        # ── Left Sidebar ──────────────────────────────────────────────
        self.sidebar = ctk.CTkFrame(self, width=220, fg_color="#080c14", corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Brand / Logo Header
        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=16, pady=(24, 16))

        ctk.CTkLabel(
            brand_frame, text="▶  YT Downloader Pro",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#f8fafc",
            anchor="w"
        ).pack(fill="x")

        ctk.CTkLabel(
            brand_frame, text=f"v{APP_VERSION}  ·  Premium Edition",
            font=ctk.CTkFont(family="Segoe UI", size=10), text_color="#475569",
            anchor="w"
        ).pack(fill="x", padx=2)

        # Separator line
        ctk.CTkFrame(self.sidebar, height=1, fg_color="#1e293b").pack(fill="x", padx=16, pady=(0, 16))

        # Sidebar Navigation Menu Items
        self.nav_items = [
            {"name": "Downloader", "icon": "⬇", "index": 0},
            {"name": "Queue", "icon": "📋", "index": 1},
            {"name": "History", "icon": "🕓", "index": 2},
            {"name": "Settings", "icon": "⚙", "index": 3},
        ]

        self._sidebar_buttons = []
        self._sidebar_indicators = []

        for item in self.nav_items:
            btn_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent", height=40)
            btn_frame.pack(fill="x", padx=12, pady=4)
            btn_frame.pack_propagate(False)

            # VS Code style left vertical indicator line
            indicator = ctk.CTkFrame(btn_frame, width=4, corner_radius=2, fg_color="transparent")
            indicator.pack(side="left", fill="y", pady=4)

            btn = ctk.CTkButton(
                btn_frame,
                text=f"  {item['icon']}   {item['name']}",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                anchor="w",
                fg_color="transparent",
                hover_color="#161b2c",
                text_color="#94a3b8",
                corner_radius=8,
                command=lambda idx=item["index"]: self._select_tab(idx)
            )
            btn.pack(side="left", fill="both", expand=True, padx=(6, 0))

            self._sidebar_buttons.append(btn)
            self._sidebar_indicators.append(indicator)

        # Bottom Sidebar Status Section
        status_sec = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        status_sec.pack(side="bottom", fill="x", padx=16, pady=20)

        # Separator line
        ctk.CTkFrame(status_sec, height=1, fg_color="#1e293b").pack(fill="x", pady=(0, 16))

        # Connectivity badge
        net_frame = ctk.CTkFrame(status_sec, fg_color="transparent")
        net_frame.pack(fill="x", pady=4)

        self._net_dot = ctk.CTkLabel(
            net_frame, text="●",
            font=ctk.CTkFont(size=14),
            text_color="#10b981",   # Emerald green
        )
        self._net_dot.pack(side="left", padx=(4, 6))

        self._net_lbl = ctk.CTkLabel(
            net_frame, text="Online Status",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#94a3b8",
        )
        self._net_lbl.pack(side="left")

        # FFmpeg badge
        ffmpeg_frame = ctk.CTkFrame(status_sec, fg_color="transparent")
        ffmpeg_frame.pack(fill="x", pady=4)

        ffmpeg_ok, _ = ffmpeg_status_message(self.settings.get("ffmpeg_path", ""))
        self._ffmpeg_dot = ctk.CTkLabel(
            ffmpeg_frame, text="●",
            font=ctk.CTkFont(size=14),
            text_color="#10b981" if ffmpeg_ok else "#f43f5e",
        )
        self._ffmpeg_dot.pack(side="left", padx=(4, 6))

        self._ffmpeg_lbl = ctk.CTkLabel(
            ffmpeg_frame, text="FFmpeg Engine",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#94a3b8",
        )
        self._ffmpeg_lbl.pack(side="left")

        # ── Right Content Area ────────────────────────────────────────
        self.right_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.right_container.pack(side="right", fill="both", expand=True)

        self.content_container = ctk.CTkFrame(self.right_container, fg_color="transparent")
        self.content_container.pack(fill="both", expand=True, padx=24, pady=(20, 4))

        # ── Instantiate tab panels ───────────────────────────────────
        self.queue_tab = QueueTab(self.content_container)
        self.history_tab = HistoryTab(self.content_container)

        self.dl_tab = DownloaderTab(
            self.content_container,
            settings     = self.settings,
            queue_tab    = self.queue_tab,
            history_tab  = self.history_tab,
        )

        self.settings_tab = SettingsTab(
            self.content_container,
            settings            = self.settings,
            on_settings_changed = self._on_settings_changed,
        )

        # ── Bottom status bar ────────────────────────────────────────
        bar = ctk.CTkFrame(self.right_container, fg_color="#080c14", height=24, corner_radius=0)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        ctk.CTkLabel(
            bar,
            text="Powered by yt-dlp  ·  FFmpeg auto-bundled  ·  For personal use only",
            font=ctk.CTkFont(family="Segoe UI", size=9), text_color="#475569",
        ).pack(side="left", padx=16)

        # Restore last selected tab index
        last_tab_idx = self.settings.get("last_tab", 0)
        if last_tab_idx not in range(len(self.nav_items)):
            last_tab_idx = 0
        self._select_tab(last_tab_idx)

    # ── Sidebar Tab Switching ─────────────────────────────────────────
    def _select_tab(self, index: int):
        self.settings["last_tab"] = index

        # Hide all panel frames
        self.dl_tab.pack_forget()
        self.queue_tab.pack_forget()
        self.history_tab.pack_forget()
        self.settings_tab.pack_forget()

        # Show active panel
        tabs = [self.dl_tab, self.queue_tab, self.history_tab, self.settings_tab]
        tabs[index].pack(fill="both", expand=True)

        # Update sidebar buttons active style
        for i, (btn, indicator) in enumerate(zip(self._sidebar_buttons, self._sidebar_indicators)):
            if i == index:
                btn.configure(
                    fg_color="#111625",
                    text_color="#3b82f6",  # Vibrant neon blue selection text
                )
                indicator.configure(fg_color="#3b82f6")  # Neon blue left highlight strip
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color="#94a3b8",
                )
                indicator.configure(fg_color="transparent")

    # ── Connectivity callbacks ─────────────────────────────────────────
    def _on_net_lost(self):
        """Called from the monitor thread — marshal to UI thread."""
        self.after(0, self._ui_net_lost)

    def _ui_net_lost(self):
        self._net_dot.configure(text_color="#f43f5e")
        self._net_lbl.configure(text_color="#f43f5e")
        if hasattr(self, "queue_tab"):
            self.queue_tab.show_no_internet()

    def _on_net_restored(self):
        self.after(0, self._ui_net_restored)

    def _ui_net_restored(self):
        self._net_dot.configure(text_color="#10b981")
        self._net_lbl.configure(text_color="#94a3b8")
        if hasattr(self, "queue_tab"):
            self.queue_tab.hide_no_internet()

    # ── Settings change ───────────────────────────────────────────────
    def _on_settings_changed(self, settings: dict):
        self.settings = settings
        self.dl_tab.settings = settings
        ffmpeg_ok, _ = ffmpeg_status_message(settings.get("ffmpeg_path", ""))
        self._ffmpeg_dot.configure(
            text_color="#10b981" if ffmpeg_ok else "#f43f5e",
        )

    # ── Close ─────────────────────────────────────────────────────────
    def _on_close(self):
        net_monitor.stop()
        save_settings(self.settings)
        self.destroy()
