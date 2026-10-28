"""
Global hotkey listener using pynput for QuickPolish.
Listens for Ctrl+Alt+R (or Cmd+Alt+R) across any desktop application.
"""

import sys
import threading
import logging
from typing import Optional, Callable
from pynput import keyboard
from .config import config
from .clipboard import capture_highlighted_text, replace_highlighted_text
from .client_api import polish_text

logger = logging.getLogger("quickpolish.hotkey")

# Platform sound notification helper
def play_sound(sound_type: str = "success") -> None:
    if not config.sound_enabled:
        return
    try:
        if sys.platform == "win32":
            import winsound
            if sound_type == "success":
                winsound.MessageBeep(winsound.MB_OK)
            elif sound_type == "alert":
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            elif sound_type == "error":
                winsound.MessageBeep(winsound.MB_ICONHAND)
        elif sys.platform == "darwin":
            # macOS bell
            print("\a", end="", flush=True)
    except Exception:
        pass

class HotkeyManager:
    """Manages global shortcut listening and background polish task execution."""

    def __init__(self, on_status_change: Optional[Callable[[str], None]] = None):
        self.listener: Optional[keyboard.GlobalHotKeys] = None
        self._lock = threading.Lock()
        self.is_busy = False
        self.on_status_change = on_status_change

    def _set_status(self, msg: str) -> None:
        if self.on_status_change:
            try:
                self.on_status_change(msg)
            except Exception as e:
                logger.debug(f"Status update callback failed: {e}")

    def _execute_polish_flow(self) -> None:
        """The complete capture -> polish -> replace lifecycle running on worker thread."""
        if self._lock.locked():
            logger.warning("QuickPolish is already processing a request. Skipping duplicate trigger.")
            return

        with self._lock:
            self.is_busy = True
            self._set_status("Capturing text...")
            logger.info("Hotkey triggered! Capturing selection via sentinel polling...")

            # 1. Capture highlighted text
            timeout_ms = int(config.get("copy_poll_timeout_ms", 400))
            success, raw_text, original_clip = capture_highlighted_text(timeout_ms=timeout_ms)

            if not success or not raw_text.strip():
                logger.info("No text was highlighted.")
                self._set_status("Ready (No text selected)")
                play_sound("alert")
                self.is_busy = False
                return

            # 2. Call Vercel Proxy backend
            tone = config.tone
            self._set_status(f"Polishing ({tone})...")
            logger.info(f"Polishing {len(raw_text)} chars with tone: {tone}")

            api_success, result_text = polish_text(raw_text, tone=tone)

            if not api_success:
                logger.error(f"Polish failed: {result_text}")
                self._set_status("Error: Rewriting failed")
                play_sound("error")
                self.is_busy = False
                return

            # 3. Paste rewritten text in place
            self._set_status("Pasting rewritten text...")
            paste_delay = int(config.get("paste_delay_ms", 60))
            replaced = replace_highlighted_text(result_text, delay_ms=paste_delay)

            if replaced:
                logger.info("In-place rewrite complete!")
                play_sound("success")
                self._set_status("Polished successfully!")
            else:
                self._set_status("Error: Failed to paste")
                play_sound("error")

            self.is_busy = False

    def on_hotkey_activated(self) -> None:
        """Called immediately upon hotkey combo press. Dispatches to worker thread."""
        threading.Thread(target=self._execute_polish_flow, daemon=True, name="QP-Worker").start()

    def start(self) -> None:
        """Starts the global hotkey listener in non-blocking mode."""
        hotkey_str = config.hotkey
        logger.info(f"Registering global hotkey: {hotkey_str}")

        hotkeys = {
            hotkey_str: self.on_hotkey_activated
        }

        try:
            self.listener = keyboard.GlobalHotKeys(hotkeys)
            self.listener.start()
            logger.info("Global hotkey listener successfully started.")
        except Exception as e:
            logger.error(f"Failed to start GlobalHotKeys with {hotkey_str}: {e}")

    def stop(self) -> None:
        """Stops the global hotkey listener."""
        if self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass
            self.listener = None
            logger.info("Global hotkey listener stopped.")
