"""大嘴怪 — 配置管理模块

基于 QSettings 持久化，封装所有配置项的读写。
"""
import os
from pathlib import Path

try:
    from PySide6.QtCore import QSettings, QStandardPaths
    _HAS_QT = True
except ImportError:
    _HAS_QT = False

APP_NAME = "大嘴怪"
ORG_NAME = "BigMouthMonster"

# ── 配置键名与默认值 ──────────────────────────────────
_DEFAULTS = {
    # 仓库
    "repo_path": str(Path.home() / "大嘴怪仓库"),
    "first_run": True,
    "language": "zh",

    # 窗口
    "window_x": -1,          # -1 表示自动定位（默认右下角）
    "window_y": -1,
    "window_scale": 1.0,
    "always_on_top": True,

    # 系统
    "autostart": False,
    "minimize_to_tray": True,

    # 投喂
    "clipboard_monitor": True,
    "auto_classify": True,

    # 知识库
    "auto_index": True,
    "watchdog_enabled": True,

    # LLM
    "llm_backend": "ollama",         # ollama | openai_compatible
    "ollama_endpoint": "http://localhost:11434",
    "ollama_model": "qwen2.5:7b",
    "api_endpoint": "https://api.openai.com/v1",
    "api_key": "",
    "api_model": "gpt-4o-mini",

    # 嵌入
    "embedding_model": "all-MiniLM-L6-v2",
    "embedding_device": "cpu",
    "max_context_chunks": "8",
    "max_history_rounds": "10",
}


class Config:
    """应用配置门面，底层用 QSettings"""

    def __init__(self):
        if _HAS_QT:
            self._settings = QSettings(ORG_NAME, APP_NAME)
            self._store: dict[str, object] = {}
            self._use_qt = True
        else:
            self._settings = None
            self._store: dict[str, object] = dict(_DEFAULTS)
            self._use_qt = False

    # ── 通用存取 ──────────────────────────────────
    def get(self, key: str, default=None):
        if self._use_qt:
            raw = self._settings.value(key)
            if raw is None:
                return default if default is not None else _DEFAULTS.get(key)
            return raw
        else:
            return self._store.get(key, default if default is not None else _DEFAULTS.get(key))

    def set(self, key: str, value) -> None:
        if self._use_qt:
            self._settings.setValue(key, value)
            self._settings.sync()
        else:
            self._store[key] = value

    # ── 类型化存取（便捷方法）──────────────────────
    @property
    def repo_path(self) -> str:
        return str(self.get("repo_path"))

    @repo_path.setter
    def repo_path(self, value: str) -> None:
        self.set("repo_path", value)

    @property
    def first_run(self) -> bool:
        v = self.get("first_run")
        return v if isinstance(v, bool) else str(v).lower() in ("true", "1", "yes")

    @first_run.setter
    def first_run(self, value: bool) -> None:
        self.set("first_run", value)

    @property
    def window_x(self) -> int:
        return int(self.get("window_x", -1))

    @window_x.setter
    def window_x(self, value: int) -> None:
        self.set("window_x", value)

    @property
    def window_y(self) -> int:
        return int(self.get("window_y", -1))

    @window_y.setter
    def window_y(self, value: int) -> None:
        self.set("window_y", value)

    @property
    def window_scale(self) -> float:
        return float(self.get("window_scale", 1.0))

    @property
    def always_on_top(self) -> bool:
        v = self.get("always_on_top")
        return v if isinstance(v, bool) else str(v).lower() in ("true", "1", "yes")

    @property
    def autostart(self) -> bool:
        v = self.get("autostart")
        return v if isinstance(v, bool) else str(v).lower() in ("true", "1", "yes")

    @autostart.setter
    def autostart(self, value: bool) -> None:
        self.set("autostart", value)

    @property
    def clipboard_monitor(self) -> bool:
        v = self.get("clipboard_monitor")
        return v if isinstance(v, bool) else str(v).lower() in ("true", "1", "yes")

    @property
    def auto_index(self) -> bool:
        v = self.get("auto_index")
        return v if isinstance(v, bool) else str(v).lower() in ("true", "1", "yes")

    @property
    def watchdog_enabled(self) -> bool:
        v = self.get("watchdog_enabled")
        return v if isinstance(v, bool) else str(v).lower() in ("true", "1", "yes")

    @property
    def llm_backend(self) -> str:
        return str(self.get("llm_backend", "ollama"))

    @llm_backend.setter
    def llm_backend(self, value: str) -> None:
        self.set("llm_backend", value)

    @property
    def ollama_endpoint(self) -> str:
        return str(self.get("ollama_endpoint", "http://localhost:11434"))

    @property
    def ollama_model(self) -> str:
        return str(self.get("ollama_model", "qwen2.5:7b"))

    @property
    def api_endpoint(self) -> str:
        return str(self.get("api_endpoint", "https://api.openai.com/v1"))

    @property
    def api_key(self) -> str:
        return str(self.get("api_key", ""))

    @api_key.setter
    def api_key(self, value: str) -> None:
        self.set("api_key", value)

    @property
    def api_model(self) -> str:
        return str(self.get("api_model", "gpt-4o-mini"))

    @property
    def embedding_model(self) -> str:
        return str(self.get("embedding_model", "all-MiniLM-L6-v2"))

    @property
    def embedding_device(self) -> str:
        return str(self.get("embedding_device", "cpu"))

    @property
    def max_context_chunks(self) -> int:
        return int(self.get("max_context_chunks", 8))

    @property
    def max_history_rounds(self) -> int:
        return int(self.get("max_history_rounds", 10))

    # ── 便捷方法 ──────────────────────────────────
    @property
    def db_path(self) -> str:
        return str(Path(self.repo_path) / "big_mouth.db")

    @property
    def chroma_path(self) -> str:
        return str(Path(self.repo_path) / "chroma_db")

    @property
    def files_path(self) -> str:
        return str(Path(self.repo_path) / "files")

    def ensure_paths(self) -> None:
        """确保所有需要的目录存在"""
        Path(self.repo_path).mkdir(parents=True, exist_ok=True)
        Path(self.files_path).mkdir(parents=True, exist_ok=True)
        Path(self.chroma_path).mkdir(parents=True, exist_ok=True)

    def all_settings(self) -> dict:
        """返回当前所有配置（用于调试/设置界面）"""
        result = {}
        for key in _DEFAULTS:
            result[key] = self.get(key)
        return result


# 全局单例（需要在 QApplication 创建后实例化）
_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
