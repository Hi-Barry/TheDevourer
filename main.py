"""大嘴怪桌面小宠物 — 入口

运行：python main.py
"""
import sys
import os
from pathlib import Path

# 将项目根目录加入 sys.path，确保包导入正常
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon, QAction

from core.config import get_config
from core.logger import init_logger, get_logger
from core.db import Database
from core.chroma_client import init_chroma
from core.feed_handler import FeedQueueWorker
from core.kb_qa import create_kb_qa
from core.storage_manager import StorageManager
from ui.pet_window import PetWindow
from ui.question_dialog import QuestionDialog
from ui.content_browser import ContentBrowser
from ui.settings_dialog import SettingsDialog


def main():
    # ── 1. 创建 QApplication ──────────────────────
    app = QApplication(sys.argv)
    app.setApplicationName("大嘴怪")
    app.setOrganizationName("BigMouthMonster")

    # ── 2. 初始化配置 ─────────────────────────────
    config = get_config()
    config.ensure_paths()

    # ── 3. 初始化日志 ─────────────────────────────
    log_dir = str(Path(config.repo_path) / "logs")
    init_logger(log_dir)
    logger = get_logger()

    logger.info("=" * 50)
    logger.info("大嘴怪启动")
    logger.info(f"仓库路径: {config.repo_path}")
    logger.info(f"首次运行: {config.first_run}")

    # ── 4. 初始化数据库 ───────────────────────────
    db = Database(config.db_path)
    db.init_schema()
    logger.info(f"数据库已初始化: {config.db_path}")

    # 验证数据库可用
    stats = db.get_stats()
    logger.info(f"仓库统计 — 内容数: {stats['total_items']}, 总大小: {stats['total_size']}")

    # ── 4.5 初始化 ChromaDB ──────────────────────
    try:
        chroma = init_chroma(config.chroma_path)
        logger.info(f"ChromaDB 已初始化: {config.chroma_path} (chunks: {chroma.count()})")
    except Exception as e:
        logger.warning(f"ChromaDB 初始化失败（向量搜索不可用）: {e}")
        chroma = None

    # ── 5. 创建精灵悬浮窗 + 投喂队列 ──────────────
    feed_queue = FeedQueueWorker()
    sm = StorageManager(db, chroma)
    pet_window = PetWindow(feed_queue=feed_queue)

    # 投喂信号日志
    pet_window.feed_received.connect(
        lambda item: logger.info(f"📥 投喂接收: {item.display_name}")
    )
    pet_window.feed_done.connect(
        lambda item, ok, msg: logger.info(f"{'✅' if ok else '❌'} {msg}")
    )

    # 剪贴板监听定时器（每 1 秒检查一次，但不自动投喂）
    clipboard_timer = QTimer()
    clipboard_timer.timeout.connect(pet_window.check_clipboard)
    clipboard_timer.start(1000)

    pet_window.show()

    # ── 5.5 初始化知识库问答 ──────────────────────
    kb_qa = create_kb_qa(db, chroma)
    question_dialog = QuestionDialog()
    question_session_id = kb_qa.new_session()

    def on_question_requested():
        question_dialog.show()
        question_dialog.raise_()

    def on_question_submitted(question: str):
        logger.info(f"🔍 提问: {question}")
        question_dialog.clear_answer()
        question_dialog.set_loading(True)

        sources_ref = []

        def on_token(token: str):
            question_dialog.append_token(token)

        def on_sources(sources: list):
            nonlocal sources_ref
            sources_ref = sources

        # 在后台线程执行问答（避免阻塞 UI）
        import threading
        def _run_qa():
            try:
                full = kb_qa.ask(question, stream_callback=on_token, on_sources=on_sources)
                kb_qa.save_conversation(question_session_id, "user", question)
                kb_qa.save_conversation(question_session_id, "assistant", full, sources_ref)
            except Exception as e:
                on_token(f"\n\n❌ 问答失败: {e}")
            finally:
                question_dialog.set_loading(False)

        threading.Thread(target=_run_qa, daemon=True).start()

    pet_window.question_requested.connect(on_question_requested)
    question_dialog.question_submitted.connect(on_question_submitted)

    # ── 5.6 初始化内容浏览器 ────────────────────
    browser = ContentBrowser(db, sm)
    pet_window.browser_requested.connect(lambda: browser.show() or browser.raise_())
    browser.show()

    # ── 5.7 系统托盘 ──────────────────────────────
    tray = QSystemTrayIcon()
    tray_icon = QIcon(str(PROJECT_ROOT / "resources" / "pet_idle.png"))
    tray.setIcon(tray_icon)
    tray.setToolTip("大嘴怪 — 桌面知识管家")

    tray_menu = QMenu()
    act_show = tray_menu.addAction("👻 显示精灵")
    act_show.triggered.connect(pet_window.show)
    act_show.triggered.connect(pet_window.raise_)
    act_open = tray_menu.addAction("📖 打开仓库")
    act_open.triggered.connect(browser.show)
    act_open.triggered.connect(browser.raise_)
    act_feed = tray_menu.addAction("📋 投喂剪贴板")
    act_feed.triggered.connect(pet_window._feed_clipboard)
    tray_menu.addSeparator()
    act_settings = tray_menu.addAction("⚙️ 设置...")
    act_settings.triggered.connect(settings_dialog.show)
    act_exit = tray_menu.addAction("❌ 退出")
    act_exit.triggered.connect(app.quit)
    tray.setContextMenu(tray_menu)

    tray.activated.connect(lambda reason: (
        (pet_window.show(), pet_window.raise_())
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None
    ))
    tray.show()

    # ── 5.8 设置对话框 ────────────────────────────
    settings_dialog = SettingsDialog()
    pet_window.settings_requested.connect(settings_dialog.show)
    settings_dialog.settings_changed.connect(browser.refresh)

    # ── 6. 事件循环 ───────────────────────────────
    exit_code = app.exec()

    # ── 7. 清理 ───────────────────────────────────
    db.close()
    logger.info("大嘴怪退出")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
