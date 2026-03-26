"""
EyeScroll 配置测试
"""
import pytest
import tempfile
import os
from pathlib import Path
from config import Config, DEFAULT_CONFIG


class TestConfig:
    """Config 配置管理测试"""

    def test_default_values(self):
        """默认配置值正确"""
        # 需要隔离测试，使用临时配置
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test_config.json"
            # 直接测试 Config 类的属性
            c = Config.__new__(Config)
            c._config = DEFAULT_CONFIG.copy()
            assert c.scroll_zone_ratio == 0.25
            assert c.dwell_time_ms == 500
            assert c.scroll_distance == 80
            assert c.scroll_interval_ms == 100
            assert c.detection_confidence == 0.5

    def test_get_returns_config_value(self):
        """get() 返回配置值"""
        c = Config.__new__(Config)
        c._config = DEFAULT_CONFIG.copy()
        assert c.get("scroll_zone_ratio") == 0.25
        assert c.get("nonexistent", "default") == "default"

    def test_set_updates_config(self):
        """set() 更新配置值"""
        c = Config.__new__(Config)
        c._config = DEFAULT_CONFIG.copy()
        c.set("scroll_distance", 100)
        assert c.scroll_distance == 100
