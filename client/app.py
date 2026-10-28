"""
QuickPolish Desktop Client - Main Application Lifecycle Entry Point.
Coordinates global hotkey hooks, system tray icon, and single-instance locks.
"""

import os
import sys
import signal
import logging
from typing import Optional

# Setup root logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("quickpolish.app")

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.config import config
from core.hotkey import HotkeyManager
from ui.tray import TrayApp
from assets.generate_icon import ensure_icons

class SingleInstanceLock:
    """Ensures only a single instance of QuickPolish runs simultaneously."""

    def __init__(self, app_name: str = "quickpolish"):
        self.app_name = app_name
        self.mutex = None
        self.lock_file = None

    def acquire(self) -> bool:
        if sys.platform == "win32":
            try:
                import win32event
                import win32api
                import winerror
                self.mutex = win32event.CreateMutex(None, False, f"Global\\{self.app_name}_SingleInstanceMutex")
                if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                    return False
                return True
            except ImportError:
                pass  # Fall back to file-based lock

        # Cross-platform file lock fallback
        lock_dir = os.path.join(os.path.expanduser("~"), ".quickpolish")
        os.makedirs(lock_dir, exist_ok=True)
        self.lock_file_path = os.path.join(lock_dir, f"{self.app_name}.lock")
        try:
            if os.path.exists(self.lock_file_path):
                # Check if process is still alive
                try:
                    with open(self.lock_file_path, "r") as f:
                        pid = int(f.read().strip())
                    if sys.platform == "win32":
                        import ctypes
                        kernel32 = ctypes.windll.kernel32
                        handle = kernel32.OpenProcess(0x1000, False, pid) # PROCESS_QUERY_LIMITED_INFORMATION
                        if handle != 0:
                            kernel32.CloseHandle(handle)
                            return False # Still running
                    else:
                        os.kill(pid, 0)
                        return False # Still running
                except Exception:
                    pass # Stale lockfile

            with open(self.lock_file_path, "w") as f:
                f.write(str(os.getpid()))
            return True
        except Exception as e:
            logger.warning(f"File lock check exception: {e}")
            return True

    def release(self) -> None:
        try:
            if hasattr(self, "lock_file_path") and os.path.exists(self.lock_file_path):
                os.remove(self.lock_file_path)
        except Exception:
            pass

def main():
    logger.info("Initializing QuickPolish Desktop Client...")

    # 1. Single instance check
    instance_lock = SingleInstanceLock()
    if not instance_lock.acquire():
        logger.warning("Another instance of QuickPolish is already running.")
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            messagebox.showinfo("QuickPolish", "QuickPolish is already running in your system tray.")
            root.destroy()
        except Exception:
            pass
        sys.exit(0)

    # 2. Ensure assets exist
    assets_dir = os.path.join(BASE_DIR, "assets")
    ensure_icons(assets_dir)

    # 3. Initialize components
    tray_app = TrayApp()
    hotkey_mgr = HotkeyManager(on_status_change=tray_app.set_status)

    def shutdown():
        logger.info("Shutting down QuickPolish...")
        hotkey_mgr.stop()
        instance_lock.release()

    tray_app.on_exit = shutdown

    # Handle OS termination signals
    def sig_handler(sig, frame):
        shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    # 4. Start global hotkey listener
    hotkey_mgr.start()
    tray_app.set_status(f"Ready ({config.tone})")

    # 5. Run system tray mainloop (blocking)
    try:
        tray_app.run()
    finally:
        shutdown()

if __name__ == "__main__":
    main()
