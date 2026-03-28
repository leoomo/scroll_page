"""
EyeScroll 配置管理
用户可调参数的存储和读取
"""
import json
from pathlib import Path

DEFAULT_CONFIG = {
    "scroll_zone_ratio": 0.20,
    "dwell_time_ms": 500,
    "scroll_distance": 30,
    "scroll_interval_ms": 200,
    "detection_confidence": 0.5,
    "up_scroll_enabled": True,
    "up_scroll_ratio": 0.10,
    "up_dwell_time_ms": 800,
    "up_scroll_distance": 30,
    "up_scroll_interval_ms": 200,
    "head_down_threshold": 0.008,
    "head_up_threshold": -0.008,
    "head_deadzone": 0.003,
    "head_ema_alpha": 0.30,
    "head_dwell_time_ms": 150,
    "head_continuous_threshold_ms": 2000,
}

CONFIG_FILE = Path.home() / ".eye_scroll" / "config.json"


class Config:
    def __init__(self):
        self._config = DEFAULT_CONFIG.copy()
        self._load()

    def _load(self):
        """从文件加载配置"""
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                self._config.update(loaded)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save(self):
        """保存配置到文件"""
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get(self, key: str, default=None):
        """获取配置值"""
        return self._config.get(key, default)

    def set(self, key: str, value):
        """设置配置值并保存"""
        self._config[key] = value
        self._save()

    @property
    def scroll_zone_ratio(self) -> float:
        return self._config["scroll_zone_ratio"]

    @property
    def dwell_time_ms(self) -> int:
        return self._config["dwell_time_ms"]

    @property
    def scroll_distance(self) -> int:
        return self._config["scroll_distance"]

    @property
    def scroll_interval_ms(self) -> int:
        return self._config["scroll_interval_ms"]

    @property
    def detection_confidence(self) -> float:
        return self._config["detection_confidence"]

    @property
    def up_scroll_enabled(self) -> bool:
        return self._config["up_scroll_enabled"]

    @property
    def up_scroll_ratio(self) -> float:
        return self._config["up_scroll_ratio"]

    @property
    def up_dwell_time_ms(self) -> int:
        return self._config["up_dwell_time_ms"]

    @property
    def up_scroll_distance(self) -> int:
        return self._config["up_scroll_distance"]

    @property
    def up_scroll_interval_ms(self) -> int:
        return self._config["up_scroll_interval_ms"]


config = Config()
