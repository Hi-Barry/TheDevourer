"""TheDevourer — 轻量启动器

初始化核心层 → ModuleLoader 动态加载全部插件 → 事件循环。
不直接 import 任何功能/UI 模块。
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication

from core.config import get_config
from core.logger import init_logger, get_logger
from core.db import Database
from core.signal_bus import EventBus
from core.module_loader import ModuleLoader


def main():
    # ── 1. QApplication ──────────────────────────
    app = QApplication(sys.argv)
    app.setApplicationName("TheDevourer")
    app.setOrganizationName("TheDevourer")

    # ── 2. 核心层初始化 ───────────────────────────
    config = get_config()
    config.ensure_paths()

    log_dir = str(Path(config.repo_path) / "logs")
    init_logger(log_dir)
    logger = get_logger()

    logger.info("=" * 50)
    logger.info("TheDevourer 启动")
    logger.info(f"仓库路径: {config.repo_path}")
    logger.info(f"首次运行: {config.first_run}")

    db = Database(config.db_path)
    db.init_schema()
    logger.info(f"数据库已初始化: {config.db_path}")

    stats = db.get_stats()
    logger.info(f"仓库统计 — 内容数: {stats['total_items']}, 总大小: {stats['total_size']}")

    # ── 3. SignalBus ─────────────────────────────
    bus = EventBus()

    # ── 4. ModuleLoader 加载全部插件 ──────────────
    loader = ModuleLoader()

    # 先尝试加载 modules/（开发模式），再尝试 plugins/（发布模式）
    modules_path = str(PROJECT_ROOT / "modules")
    plugins_path = str(PROJECT_ROOT / "plugins")

    loaded = {}
    if Path(modules_path).exists():
        loaded = loader.load_all(modules_path)
    elif Path(plugins_path).exists():
        loaded = loader.load_all(plugins_path)

    if loaded:
        logger.info(f"已加载 {len(loaded)} 个模块: {', '.join(loaded.keys())}")
    else:
        logger.info("无可用模块，以核心模式运行")

    # ── 5. 事件循环 ───────────────────────────────
    exit_code = app.exec()

    # ── 6. 清理 ───────────────────────────────────
    loader.cleanup()
    db.close()
    logger.info("TheDevourer 退出")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
