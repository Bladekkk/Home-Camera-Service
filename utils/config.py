"""Загрузка и сохранение настроек."""

import json
import os
from utils.logger import Logger

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

DEFAULT_CONFIG = {
    "camera_index": 0,
    "port": 3222,
    "segment_duration_minutes": 5,
}


def load_config() -> dict:
    """Загружает настройки из JSON файла, если он существует и корректен."""
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for key in DEFAULT_CONFIG:
            if key not in cfg:
                return None
        if not isinstance(cfg["camera_index"], int) or cfg["camera_index"] < 0:
            return None
        if not isinstance(cfg["port"], int) or cfg["port"] < 1 or cfg["port"] > 65535:
            return None
        if not isinstance(cfg["segment_duration_minutes"], int) or cfg["segment_duration_minutes"] < 1:
            return None
        return cfg
    except (json.JSONDecodeError, OSError):
        return None


def save_config(camera_index: int, port: int, segment_duration_minutes: int):
    """Сохраняет настройки в JSON файл."""
    cfg = {
        "camera_index": camera_index,
        "port": port,
        "segment_duration_minutes": segment_duration_minutes,
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        Logger.log(f"Настройки сохранены в {CONFIG_FILE}")
    except OSError as e:
        Logger.log(f"Ошибка сохранения настроек: {e}")
