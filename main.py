"""
main.py
Entry point for YT Downloader Pro.
Sets DPI awareness on Windows and launches the application.
"""

import sys
import os

# ── High-DPI awareness (Windows) ────────────────────────────────────────────
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

# ── Ensure local packages are on path ───────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

# ── Launch ───────────────────────────────────────────────────────────────────
from ui.app import App


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
