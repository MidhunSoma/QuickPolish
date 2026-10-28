"""
Active polling, UUID sentinel & paste replacement engine for QuickPolish.
Ensures zero-loss text capture from any desktop application without API dependencies.
"""

import sys
import time
import uuid
import logging
from typing import Tuple, Optional
import pyperclip
from pynput.keyboard import Controller, Key

logger = logging.getLogger("quickpolish.clipboard")
keyboard = Controller()

IS_MAC = sys.platform == "darwin"
MODIFIER_KEY = Key.cmd if IS_MAC else Key.ctrl

def _safe_get_clipboard() -> str:
    """Reads clipboard text with retry to prevent clipboard locking issues."""
    for _ in range(5):
        try:
            return pyperclip.paste()
        except Exception:
            time.sleep(0.015)
    return ""

def _safe_set_clipboard(text: str) -> bool:
    """Writes to clipboard with retry to prevent clipboard locking issues."""
    for _ in range(5):
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            time.sleep(0.015)
    return False

def simulate_copy() -> None:
    """Simulates system copy shortcut (Ctrl+C on Win/Linux, Cmd+C on macOS)."""
    try:
        with keyboard.pressed(MODIFIER_KEY):
            keyboard.press('c')
            time.sleep(0.02)
            keyboard.release('c')
    except Exception as e:
        logger.error(f"Error simulating copy shortcut: {e}")

def simulate_paste() -> None:
    """Simulates system paste shortcut (Ctrl+V on Win/Linux, Cmd+V on macOS)."""
    try:
        with keyboard.pressed(MODIFIER_KEY):
            keyboard.press('v')
            time.sleep(0.02)
            keyboard.release('v')
    except Exception as e:
        logger.error(f"Error simulating paste shortcut: {e}")

def capture_highlighted_text(timeout_ms: int = 400) -> Tuple[bool, str, str]:
    """
    Captures currently selected text in whatever application is active using a UUID sentinel.
    
    Returns:
        (success: bool, captured_text: str, original_clipboard: str)
    """
    original_clip = _safe_get_clipboard()
    sentinel = f"__QP_SENTINEL_{uuid.uuid4().hex}__"
    
    # 1. Arm clipboard with sentinel
    _safe_set_clipboard(sentinel)
    time.sleep(0.03)

    # 2. Trigger native OS copy shortcut
    simulate_copy()

    # 3. Active polling loop: wait for clipboard content to change away from sentinel
    deadline = time.time() + (timeout_ms / 1000.0)
    captured_text = ""
    success = False

    while time.time() < deadline:
        current_val = _safe_get_clipboard()
        if current_val != sentinel:
            captured_text = current_val
            success = True
            break
        time.sleep(0.02)

    if not success:
        logger.info("Clipboard polling timed out: No active text selection detected.")
        # Restore original clipboard
        _safe_set_clipboard(original_clip)
        return False, "", original_clip

    # Validate captured content is non-empty
    if not captured_text.strip():
        logger.info("Captured text is only whitespace.")
        _safe_set_clipboard(original_clip)
        return False, "", original_clip

    logger.info(f"Successfully captured {len(captured_text)} chars from active application.")
    return True, captured_text, original_clip

def replace_highlighted_text(new_text: str, delay_ms: int = 60) -> bool:
    """
    Pastes the newly polished text directly over the active selection in-place.
    """
    # 1. Stage polished text onto clipboard
    if not _safe_set_clipboard(new_text):
        logger.error("Failed to set rewritten text to clipboard.")
        return False
        
    time.sleep(delay_ms / 1000.0)

    # 2. Fire native OS paste shortcut
    simulate_paste()

    # Allow target window time to ingest the paste event
    time.sleep(0.08)
    logger.info("Polished text successfully pasted into active application.")
    return True
