import json
import os
import base64
from pathlib import Path


APP_DATA_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "EpubTranslator"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = APP_DATA_DIR / "config.json"

DEFAULT_CONFIG = {
    "last_output_folder": "",
    "default_src_language": "ko",
    "default_method": "google",
    "google_chunk_size": 5,
    "google_style": "neutral",
    "google_auto_optimize": True,
    "openrouter_api_key": "",
    "openrouter_model": "google/gemini-2.0-flash-exp:free",
    "openrouter_temperature": 0.3,
    "openrouter_system_prompt": "",
    "groq_api_key": "",
    "groq_model": "llama-3.1-8b-instant",
    "groq_temperature": 0.3,
    "groq_system_prompt": "",
}


class ConfigManager:
    def __init__(self):
        self._config = self._load()

    def _load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                merged = DEFAULT_CONFIG.copy()
                merged.update(saved)
                return merged
            except (json.JSONDecodeError, IOError):
                return DEFAULT_CONFIG.copy()
        return DEFAULT_CONFIG.copy()

    def _save(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

    def get(self, key, default=None):
        return self._config.get(key, default)

    def set(self, key, value):
        self._config[key] = value
        self._save()

    def get_all(self):
        return self._config.copy()

    def get_openrouter_api_key(self):
        encoded = self._config.get("openrouter_api_key", "")
        if not encoded:
            return ""
        try:
            return base64.b64decode(encoded).decode("utf-8")
        except Exception:
            return encoded

    def set_openrouter_api_key(self, key):
        if key:
            encoded = base64.b64encode(key.encode("utf-8")).decode("utf-8")
        else:
            encoded = ""
        self._config["openrouter_api_key"] = encoded
        self._save()

    def get_groq_api_key(self):
        encoded = self._config.get("groq_api_key", "")
        if not encoded:
            return ""
        try:
            return base64.b64decode(encoded).decode("utf-8")
        except Exception:
            return encoded

    def set_groq_api_key(self, key):
        if key:
            encoded = base64.b64encode(key.encode("utf-8")).decode("utf-8")
        else:
            encoded = ""
        self._config["groq_api_key"] = encoded
        self._save()
