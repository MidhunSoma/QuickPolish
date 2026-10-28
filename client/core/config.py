import os
import sys
import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger("quickpolish.config")

DEFAULT_TONES: List[str] = [
    "Professional",
    "Casual",
    "Concise",
    "Executive",
    "Grammar Only",
    "Bullet Points",
]

def get_default_hotkey() -> str:
    """Returns platform-aware default global hotkey string."""
    if sys.platform == "darwin":
        return "<cmd>+<alt>+r"
    return "<ctrl>+<alt>+r"

DEFAULT_CONFIG: Dict[str, Any] = {
    "proxy_url": "https://quickpolish-proxy.vercel.app",
    "tone": "Professional",
    "hotkey": get_default_hotkey(),
    "sound_enabled": True,
    "notifications_enabled": True,
    "copy_poll_timeout_ms": 400,
    "paste_delay_ms": 60,
    "request_timeout_sec": 12,
}

class ConfigManager:
    """Manages persistent QuickPolish user settings in ~/.quickpolish/config.json."""

    def __init__(self):
        self.config_dir = os.path.join(os.path.expanduser("~"), ".quickpolish")
        self.config_file = os.path.join(self.config_dir, "config.json")
        self.config: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        """Loads configuration from JSON file or initializes defaults."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        self.config.update(loaded)
                        logger.info(f"Loaded config from {self.config_file}")
            else:
                self.save()
        except Exception as e:
            logger.warning(f"Failed to load config from {self.config_file}: {e}. Using defaults.")

    def save(self) -> None:
        """Persists current configuration to disk."""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Saved config to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving config to {self.config_file}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.config[key] = value
        self.save()

    @property
    def proxy_url(self) -> str:
        return str(self.config.get("proxy_url", DEFAULT_CONFIG["proxy_url"])).rstrip("/")

    @proxy_url.setter
    def proxy_url(self, val: str) -> None:
        self.set("proxy_url", val.rstrip("/"))

    @property
    def tone(self) -> str:
        tone = self.config.get("tone", "Professional")
        return tone if tone in DEFAULT_TONES else "Professional"

    @tone.setter
    def tone(self, val: str) -> None:
        if val in DEFAULT_TONES:
            self.set("tone", val)

    @property
    def hotkey(self) -> str:
        return str(self.config.get("hotkey", get_default_hotkey()))

    @property
    def sound_enabled(self) -> bool:
        return bool(self.config.get("sound_enabled", True))

# Global singleton instance
config = ConfigManager()
