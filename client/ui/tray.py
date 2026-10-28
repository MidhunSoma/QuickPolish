"""
pystray system tray menu and status manager for QuickPolish.
Allows easy tone selection, proxy configuration, and live status display.
"""

import os
import sys
import threading
import logging
from typing import Optional, Callable
from PIL import Image
import pystray
from pystray import MenuItem as item, Menu

from ..core.config import config, DEFAULT_TONES
from ..core.client_api import polish_text, test_connection
from ..core.clipboard import _safe_get_clipboard, _safe_set_clipboard
from ..assets.generate_icon import ensure_icons

logger = logging.getLogger("quickpolish.tray")

class TrayApp:
    """Manages the desktop system tray icon and interactive menu."""

    def __init__(self, on_exit: Optional[Callable[[], None]] = None):
        self.icon: Optional[pystray.Icon] = None
        self.on_exit = on_exit
        self.status_message = "Ready"
        self._image = self._load_or_generate_icon()

    def _load_or_generate_icon(self) -> Image.Image:
        """Finds or generates the QuickPolish tray icon."""
        # Locate assets directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.abspath(os.path.join(current_dir, "..", "assets"))
        png_path = os.path.join(assets_dir, "icon.png")

        if not os.path.exists(png_path):
            logger.info("Icon not found on disk. Generating dynamically...")
            png_path, _ = ensure_icons(assets_dir)

        try:
            return Image.open(png_path)
        except Exception as e:
            logger.error(f"Failed to load icon image: {e}")
            # Fallback plain colored image
            return Image.new("RGBA", (64, 64), (99, 102, 241, 255))

    def set_status(self, status: str) -> None:
        """Updates the current status string and tray tooltip."""
        self.status_message = status
        if self.icon:
            self.icon.title = f"QuickPolish: {status} ({config.tone})"
            # Refresh menu
            self.icon.update_menu()

    def _set_tone(self, tone_name: str) -> None:
        """Callback when user selects a tone from the tray menu."""
        logger.info(f"User selected tone: {tone_name}")
        config.tone = tone_name
        self.set_status(f"Ready ({tone_name})")

    def _make_tone_setter(self, tone_name: str):
        return lambda icon, item: self._set_tone(tone_name)

    def _is_tone_checked(self, tone_name: str):
        return lambda item: config.tone == tone_name

    def _prompt_change_proxy(self) -> None:
        """Opens a lightweight native dialog to edit the Vercel proxy URL."""
        def _gui_worker():
            try:
                import tkinter as tk
                from tkinter import simpledialog, messagebox

                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)

                current_url = config.proxy_url
                new_url = simpledialog.askstring(
                    "QuickPolish - Proxy Settings",
                    "Enter your Vercel Proxy URL:\n(e.g., https://quickpolish-proxy.vercel.app)",
                    initialvalue=current_url,
                    parent=root
                )

                if new_url and new_url.strip():
                    cleaned = new_url.strip().rstrip("/")
                    config.proxy_url = cleaned
                    # Test connection
                    ok, msg = test_connection(cleaned)
                    if ok:
                        messagebox.showinfo("QuickPolish", f"Proxy updated successfully!\n{msg}")
                    else:
                        messagebox.showwarning("QuickPolish", f"Proxy saved, but test failed:\n{msg}")
                root.destroy()
            except Exception as e:
                logger.error(f"Failed to open proxy settings dialog: {e}")

        threading.Thread(target=_gui_worker, daemon=True).start()

    def _test_polish_clipboard(self) -> None:
        """Manually polishes whatever is currently stored in clipboard."""
        def _worker():
            clip_text = _safe_get_clipboard()
            if not clip_text or not clip_text.strip():
                self.set_status("Clipboard is empty!")
                return
            self.set_status(f"Polishing clipboard ({config.tone})...")
            ok, result = polish_text(clip_text, tone=config.tone)
            if ok:
                _safe_set_clipboard(result)
                self.set_status("Clipboard Polished!")
            else:
                self.set_status(f"Error: {result[:30]}")

        threading.Thread(target=_worker, daemon=True).start()

    def _show_about(self) -> None:
        """Displays helpful usage info."""
        def _worker():
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                hk = config.hotkey.upper()
                msg = (
                    f"QuickPolish v1.0.0\n"
                    f"Production Zero-Config In-place AI Rewriter\n\n"
                    f"HOW TO USE:\n"
                    f"1. Highlight rough text in ANY desktop app\n"
                    f"   (Slack, Teams, Email, Chrome, Word, Terminal, etc.)\n"
                    f"2. Press hotkey: {hk}\n"
                    f"3. Text is instantly rewritten in-place!\n\n"
                    f"Current Tone: {config.tone}\n"
                    f"Proxy URL: {config.proxy_url}"
                )
                messagebox.showinfo("About QuickPolish", msg)
                root.destroy()
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def _on_quit_clicked(self, icon, item) -> None:
        """Handles application shutdown."""
        logger.info("Quit clicked from tray menu.")
        if self.on_exit:
            self.on_exit()
        if self.icon:
            self.icon.stop()

    def _build_menu(self) -> Menu:
        """Constructs the system tray menu structure."""
        tone_items = [
            item(
                tone,
                self._make_tone_setter(tone),
                checked=self._is_tone_checked(tone),
                radio=True
            )
            for tone in DEFAULT_TONES
        ]

        hotkey_label = config.hotkey.upper().replace("<", "").replace(">", "")

        return Menu(
            item(lambda text: f"Status: {self.status_message}", None, enabled=False),
            Menu.SEPARATOR,
            item("Selected Tone", Menu(*tone_items)),
            item(f"Hotkey: {hotkey_label}", lambda icon, item: None, enabled=False),
            Menu.SEPARATOR,
            item("Polish Current Clipboard", lambda icon, item: self._test_polish_clipboard()),
            item("Configure Proxy URL...", lambda icon, item: self._prompt_change_proxy()),
            item("About QuickPolish", lambda icon, item: self._show_about()),
            Menu.SEPARATOR,
            item("Quit QuickPolish", self._on_quit_clicked),
        )

    def run(self) -> None:
        """Starts the system tray icon (blocking loop)."""
        menu = self._build_menu()
        self.icon = pystray.Icon(
            name="QuickPolish",
            icon=self._image,
            title=f"QuickPolish: Ready ({config.tone})",
            menu=menu
        )
        logger.info("QuickPolish system tray icon initialized.")
        self.icon.run()

    def stop(self) -> None:
        """Stops the system tray loop."""
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
