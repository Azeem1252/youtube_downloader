"""
ui/tab_settings.py
Settings panel — preferences, FFmpeg, proxy, output, themes in beautiful card frames.
"""

import customtkinter as ctk
from tkinter import filedialog
from utils.settings_manager import load_settings, save_settings, reset_settings
from utils.ffmpeg_checker import ffmpeg_status_message


class SettingsTab(ctk.CTkFrame):
    def __init__(self, parent, settings: dict, on_settings_changed=None):
        super().__init__(parent, fg_color="transparent")
        self.settings = settings
        self.on_settings_changed = on_settings_changed
        self._current_card = None
        self._build()

    def _build(self):
        # Scrollable inner frame
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=4, pady=4)

        self._section("📂  Output Directories & Naming")
        self._output_section()

        self._section("🎬  Download Formats & Quality Defaults")
        self._defaults_section()

        self._section("📝  Subtitle Preferences")
        self._subtitle_section()

        self._section("🔧  FFmpeg Transcoding Engine")
        self._ffmpeg_section()

        self._section("🌐  Network & Browser Session Cookies")
        self._network_section()

        self._section("🎨  Appearance & System Themes")
        self._appearance_section()

        # Save / Reset buttons row
        btn_row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        btn_row.pack(fill="x", pady=(24, 12), padx=6)

        ctk.CTkButton(
            btn_row, text="💾  Save Settings", width=160, height=38,
            fg_color="#10b981", hover_color="#059669",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._save,
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            btn_row, text="↺  Reset Defaults", width=160, height=38,
            fg_color="#271b1c", hover_color="#7f1d1d",
            text_color="#f43f5e",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._reset,
        ).pack(side="left")

    # ------------------------------------------------------------------
    def _section(self, title: str):
        # Create a card container for this section
        self._current_card = ctk.CTkFrame(
            self.scroll, fg_color="#111625", corner_radius=12,
            border_width=1, border_color="#1e293b"
        )
        self._current_card.pack(fill="x", pady=8, padx=6)

        ctk.CTkLabel(
            self._current_card, text=f"   {title}",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#93c5fd",
            anchor="w"
        ).pack(fill="x", padx=12, pady=(12, 8))

        # Horizontal separator line
        ctk.CTkFrame(self._current_card, height=1, fg_color="#1e293b").pack(fill="x", padx=14, pady=(0, 6))

    def _row(self, label: str) -> ctk.CTkFrame:
        row = ctk.CTkFrame(self._current_card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(
            row, text=label, width=180, anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#cbd5e1"
        ).pack(side="left")
        return row

    # ------------------------------------------------------------------
    def _output_section(self):
        row = self._row("Output folder:")
        self._output_var = ctk.StringVar(value=self.settings.get("output_dir", ""))
        ctk.CTkEntry(
            row, textvariable=self._output_var, width=320, height=30,
            border_color="#1e293b", fg_color="#0d111d", text_color="#f8fafc"
        ).pack(side="left", padx=(0, 8))
        
        ctk.CTkButton(
            row, text="Browse", width=80, height=30,
            fg_color="#1e293b", hover_color="#334155",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._browse_output
        ).pack(side="left")

        row2 = self._row("Filename template:")
        self._tmpl_var = ctk.StringVar(value=self.settings.get("filename_template", "%(title)s.%(ext)s"))
        ctk.CTkEntry(
            row2, textvariable=self._tmpl_var, width=320, height=30,
            border_color="#1e293b", fg_color="#0d111d", text_color="#f8fafc",
            placeholder_text="%(title)s.%(ext)s"
        ).pack(side="left")

        row3 = self._row("Organize by channel:")
        self._org_var = ctk.BooleanVar(value=self.settings.get("organize_by_channel", False))
        ctk.CTkSwitch(row3, text="", variable=self._org_var, progress_color="#3b82f6").pack(side="left", pady=4)

        row4 = self._row("Skip already downloaded:")
        self._dedup_var = ctk.BooleanVar(value=self.settings.get("avoid_duplicates", True))
        ctk.CTkSwitch(row4, text="", variable=self._dedup_var, progress_color="#3b82f6").pack(side="left", pady=4)

    def _defaults_section(self):
        from downloader import QUALITY_MAP, FORMAT_EXT_MAP
        
        dropdown_styles = {
            "fg_color": "#1e293b",
            "button_color": "#1e293b",
            "button_hover_color": "#334155",
            "dropdown_fg_color": "#0f172a",
            "dropdown_hover_color": "#1e293b",
            "text_color": "#f8fafc",
            "font": ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        }

        row = self._row("Default quality:")
        self._qual_var = ctk.StringVar(value=self.settings.get("default_quality", "1080p"))
        ctk.CTkOptionMenu(row, variable=self._qual_var,
                          values=list(QUALITY_MAP.keys()), width=160, **dropdown_styles).pack(side="left")

        row2 = self._row("Default format:")
        self._fmt_var = ctk.StringVar(value=self.settings.get("default_format", "mp4"))
        ctk.CTkOptionMenu(row2, variable=self._fmt_var,
                          values=list(FORMAT_EXT_MAP.keys()), width=160, **dropdown_styles).pack(side="left")

        row3 = self._row("Concurrent downloads:")
        self._concur_var = ctk.IntVar(value=self.settings.get("concurrent_downloads", 2))
        ctk.CTkSlider(row3, from_=1, to=5, number_of_steps=4,
                      variable=self._concur_var, width=200, progress_color="#3b82f6").pack(side="left", padx=(0, 12), pady=8)
        self._concur_lbl = ctk.CTkLabel(row3, textvariable=self._concur_var, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#3b82f6")
        self._concur_lbl.pack(side="left")

        row4 = self._row("Rate limit:")
        self._rate_var = ctk.StringVar(value=self.settings.get("rate_limit", ""))
        ctk.CTkEntry(row4, textvariable=self._rate_var, width=160, height=30,
                     border_color="#1e293b", fg_color="#0d111d", text_color="#f8fafc",
                     placeholder_text="e.g. 2M, 500K (blank = unlimited)").pack(side="left")

    def _subtitle_section(self):
        row = self._row("Default subtitle lang:")
        self._sublang_var = ctk.StringVar(value=self.settings.get("subtitle_lang", "en"))
        ctk.CTkEntry(row, textvariable=self._sublang_var, width=160, height=30,
                     border_color="#1e293b", fg_color="#0d111d", text_color="#f8fafc",
                     placeholder_text="en").pack(side="left")

        row2 = self._row("Embed subs into video:")
        self._embedsub_var = ctk.BooleanVar(value=self.settings.get("embed_subtitles", False))
        ctk.CTkSwitch(row2, text="", variable=self._embedsub_var, progress_color="#3b82f6").pack(side="left", pady=4)

        row3 = self._row("Include auto-captions:")
        self._autosub_var = ctk.BooleanVar(value=self.settings.get("auto_subtitles", True))
        ctk.CTkSwitch(row3, text="", variable=self._autosub_var, progress_color="#3b82f6").pack(side="left", pady=4)

    def _ffmpeg_section(self):
        row = self._row("FFmpeg path:")
        self._ffmpeg_var = ctk.StringVar(value=self.settings.get("ffmpeg_path", ""))
        ctk.CTkEntry(row, textvariable=self._ffmpeg_var, width=320, height=30,
                     border_color="#1e293b", fg_color="#0d111d", text_color="#f8fafc",
                     placeholder_text="Leave blank to use system PATH").pack(side="left", padx=(0, 8))
        
        ctk.CTkButton(
            row, text="Test", width=70, height=30,
            fg_color="#1e293b", hover_color="#334155",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._test_ffmpeg
        ).pack(side="left")

        self._ffmpeg_status = ctk.CTkLabel(
            self._current_card, text="", wraplength=580, justify="left",
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self._ffmpeg_status.pack(anchor="w", padx=16, pady=(2, 12))
        self._test_ffmpeg()

    def _network_section(self):
        dropdown_styles = {
            "fg_color": "#1e293b",
            "button_color": "#1e293b",
            "button_hover_color": "#334155",
            "dropdown_fg_color": "#0f172a",
            "dropdown_hover_color": "#1e293b",
            "text_color": "#f8fafc",
            "font": ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        }

        row = self._row("Proxy:")
        self._proxy_var = ctk.StringVar(value=self.settings.get("proxy", ""))
        ctk.CTkEntry(row, textvariable=self._proxy_var, width=320, height=30,
                     border_color="#1e293b", fg_color="#0d111d", text_color="#f8fafc",
                     placeholder_text="http://host:port or socks5://host:port").pack(side="left")

        row2 = self._row("Browser cookies:")
        saved_cookies = self.settings.get("cookies_browser", "")
        self._cookies_browser_var = ctk.StringVar(value=saved_cookies if saved_cookies else "None")
        ctk.CTkOptionMenu(
            row2, variable=self._cookies_browser_var,
            values=["None", "chrome", "firefox", "edge", "opera", "brave", "safari", "vivaldi", "chromium"],
            width=160, **dropdown_styles
        ).pack(side="left")

    def _appearance_section(self):
        dropdown_styles = {
            "fg_color": "#1e293b",
            "button_color": "#1e293b",
            "button_hover_color": "#334155",
            "dropdown_fg_color": "#0f172a",
            "dropdown_hover_color": "#1e293b",
            "text_color": "#f8fafc",
            "font": ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        }

        row = self._row("Color theme:")
        self._theme_var = ctk.StringVar(value=self.settings.get("theme", "dark"))
        ctk.CTkOptionMenu(row, variable=self._theme_var,
                          values=["dark", "light", "system"],
                          command=self._change_theme, width=120, **dropdown_styles).pack(side="left", pady=6)

    # ------------------------------------------------------------------
    def _browse_output(self):
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            self._output_var.set(d)

    def _test_ffmpeg(self):
        ok, msg = ffmpeg_status_message(self._ffmpeg_var.get())
        self._ffmpeg_status.configure(
            text=msg,
            text_color="#10b981" if ok else "#f43f5e",
        )

    def _change_theme(self, value):
        ctk.set_appearance_mode(value)

    def _save(self):
        cookies_val = self._cookies_browser_var.get()
        self.settings.update({
            "output_dir":         self._output_var.get(),
            "filename_template":  self._tmpl_var.get(),
            "organize_by_channel": self._org_var.get(),
            "avoid_duplicates":   self._dedup_var.get(),
            "default_quality":    self._qual_var.get(),
            "default_format":     self._fmt_var.get(),
            "concurrent_downloads": int(self._concur_var.get()),
            "rate_limit":         self._rate_var.get(),
            "subtitle_lang":      self._sublang_var.get(),
            "embed_subtitles":    self._embedsub_var.get(),
            "auto_subtitles":     self._autosub_var.get(),
            "ffmpeg_path":        self._ffmpeg_var.get(),
            "proxy":              self._proxy_var.get(),
            "cookies_browser":    "" if cookies_val == "None" else cookies_val,
            "theme":              self._theme_var.get(),
        })
        save_settings(self.settings)
        if self.on_settings_changed:
            self.on_settings_changed(self.settings)

    def _reset(self):
        s = reset_settings()
        self.settings.update(s)
        # Refresh all vars
        self._output_var.set(s.get("output_dir", ""))
        self._tmpl_var.set(s.get("filename_template", ""))
        self._qual_var.set(s.get("default_quality", "1080p"))
        self._fmt_var.set(s.get("default_format", "mp4"))
        self._proxy_var.set(s.get("proxy", ""))
        saved_cookies = s.get("cookies_browser", "")
        self._cookies_browser_var.set(saved_cookies if saved_cookies else "None")
        self._rate_var.set(s.get("rate_limit", ""))
        self._sublang_var.set(s.get("subtitle_lang", "en"))
        self._embedsub_var.set(s.get("embed_subtitles", False))
        self._autosub_var.set(s.get("auto_subtitles", True))
        self._ffmpeg_var.set(s.get("ffmpeg_path", ""))
        self._concur_var.set(s.get("concurrent_downloads", 2))
        self._org_var.set(s.get("organize_by_channel", False))
        self._dedup_var.set(s.get("avoid_duplicates", True))
        save_settings(self.settings)
        if self.on_settings_changed:
            self.on_settings_changed(self.settings)
