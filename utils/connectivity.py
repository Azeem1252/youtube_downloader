"""
utils/connectivity.py
Internet connectivity monitor — lightweight TCP probe to 8.8.8.8:53.
Fires registered callbacks when connection is lost or restored.
Module-level singleton `monitor` is shared across the whole app.
"""

import socket
import threading
import time
from typing import Callable, List, Optional


class ConnectivityMonitor:
    """
    Background thread probes internet every `check_interval` seconds.
    Thread-safe callback registration and state querying.
    """

    _TEST_HOSTS = [("8.8.8.8", 53), ("1.1.1.1", 53), ("9.9.9.9", 53)]
    _TIMEOUT = 3.0

    def __init__(self, check_interval: float = 4.0):
        self._interval = check_interval
        self._connected: bool = True   # optimistic default
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._on_lost_cbs:     List[Callable] = []
        self._on_restored_cbs: List[Callable] = []
        # Event set whenever internet is restored — lets threads wake up
        self._restore_event = threading.Event()

    # ── Callback registration ─────────────────────────────────────────
    def on_lost(self, cb: Callable) -> None:
        """Register a callback fired when connection is lost."""
        self._on_lost_cbs.append(cb)

    def on_restored(self, cb: Callable) -> None:
        """Register a callback fired when connection is restored."""
        self._on_restored_cbs.append(cb)

    # ── Control ───────────────────────────────────────────────────────
    def start(self) -> None:
        """Start monitoring in a background daemon thread."""
        if self._running:
            return
        # Do an immediate probe so the initial state is accurate
        self._connected = self._probe()
        if self._connected:
            self._restore_event.set()
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="ConnectivityMonitor"
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    # ── Status ────────────────────────────────────────────────────────
    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def wait_for_connection(self, poll_interval: float = 1.0) -> None:
        """Block the calling thread until internet is reachable."""
        while not self.is_connected:
            self._restore_event.wait(timeout=poll_interval)
            self._restore_event.clear()

    # ── Internal ──────────────────────────────────────────────────────
    def _probe(self) -> bool:
        for host, port in self._TEST_HOSTS:
            try:
                sock = socket.create_connection((host, port), timeout=self._TIMEOUT)
                sock.close()
                return True
            except OSError:
                continue
        return False

    def _loop(self) -> None:
        while self._running:
            time.sleep(self._interval)
            reachable = self._probe()
            with self._lock:
                changed = reachable != self._connected
                self._connected = reachable

            if changed:
                if reachable:
                    self._restore_event.set()
                    for cb in list(self._on_restored_cbs):
                        try:
                            cb()
                        except Exception as e:
                            print(f"[Connectivity] on_restored callback error: {e}")
                else:
                    self._restore_event.clear()
                    for cb in list(self._on_lost_cbs):
                        try:
                            cb()
                        except Exception as e:
                            print(f"[Connectivity] on_lost callback error: {e}")


# ── Module-level singleton ────────────────────────────────────────────
# Import this and call monitor.start() once from main.py
monitor = ConnectivityMonitor(check_interval=4.0)
