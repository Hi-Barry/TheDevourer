"""大嘴怪 — 文件监听与自动索引

watchdog 守护线程：监听仓库目录变化，自动触发文本提取→向量化。
"""
import time
from pathlib import Path
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from core.logger import get_logger

logger = get_logger()

# 使用 Signal 需要 PySide6；非 GUI 环境下用回调函数代替
try:
    from PySide6.QtCore import QObject, Signal
    _HAS_QT = True
except ImportError:
    _HAS_QT = False


class RepoWatcherHandler(FileSystemEventHandler):
    """仓库文件系统事件处理器"""

    def __init__(self, on_new_file=None, on_modified=None, on_deleted=None):
        super().__init__()
        self.on_new_file = on_new_file or (lambda p: None)
        self.on_modified = on_modified or (lambda p: None)
        self.on_deleted = on_deleted or (lambda p: None)
        self._debounce: dict[str, float] = {}  # 防抖：路径 → 上次事件时间

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = event.src_path
        if self._should_skip(path):
            return
        if not self._debounce_check(path):
            return
        logger.debug(f"watchdog: created {path}")
        self.on_new_file(path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = event.src_path
        if self._should_skip(path):
            return
        if not self._debounce_check(path):
            return
        logger.debug(f"watchdog: modified {path}")
        self.on_modified(path)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = event.src_path
        if self._should_skip(path):
            return
        logger.debug(f"watchdog: deleted {path}")
        self.on_deleted(path)

    def _should_skip(self, path: str) -> bool:
        """跳过非内容文件"""
        name = Path(path).name
        # 跳过隐藏文件、临时文件、数据库文件
        if name.startswith("."):
            return True
        if name.endswith((".tmp", ".temp", ".swp", ".lock")):
            return True
        if name in ("big_mouth.db", "big_mouth.db-wal", "big_mouth.db-shm"):
            return True
        # 跳过 chroma_db 目录
        if "chroma_db" in path:
            return True
        # 跳过缩略图缓存
        if ".thumbnails" in path:
            return True
        return False

    def _debounce_check(self, path: str, cooldown: float = 2.0) -> bool:
        """防抖：同一文件 2 秒内不重复处理"""
        now = time.time()
        last = self._debounce.get(path, 0)
        if now - last < cooldown:
            return False
        self._debounce[path] = now
        return True


class FileWatcher:
    """文件监听器，封装 watchdog Observer"""

    def __init__(self, watch_dir: str, storage_manager=None):
        self.watch_dir = str(watch_dir)
        self.storage_manager = storage_manager
        self._observer: Optional[Observer] = None
        self._handler: Optional[RepoWatcherHandler] = None
        self._running = False

        # 统计
        self.stats = {
            "files_created": 0,
            "files_modified": 0,
            "files_deleted": 0,
            "files_indexed": 0,
            "index_errors": 0,
        }

    # ── 启动/停止 ─────────────────────────────────

    def start(self) -> None:
        """启动文件监听"""
        if self._running:
            return

        # 确保目录存在
        Path(self.watch_dir).mkdir(parents=True, exist_ok=True)

        # 创建事件处理器
        self._handler = RepoWatcherHandler(
            on_new_file=self._on_new_file,
            on_modified=self._on_file_modified,
            on_deleted=self._on_file_deleted,
        )

        # 启动 Observer
        self._observer = Observer()
        self._observer.schedule(self._handler, self.watch_dir, recursive=True)
        self._observer.start()
        self._running = True
        logger.info(f"watchdog 已启动，监听: {self.watch_dir}")

        # 启动时全量扫描补齐
        self.full_scan()

    def stop(self) -> None:
        """停止文件监听"""
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=5)
        self._running = False
        logger.info("watchdog 已停止")

    # ── 事件处理 ──────────────────────────────────

    def _on_new_file(self, path: str) -> None:
        self.stats["files_created"] += 1
        self._schedule_index(path, reason="created")

    def _on_file_modified(self, path: str) -> None:
        self.stats["files_modified"] += 1
        self._schedule_index(path, reason="modified")

    def _on_file_deleted(self, path: str) -> None:
        self.stats["files_deleted"] += 1
        self._cleanup_deleted(path)

    def _schedule_index(self, path: str, reason: str = "") -> None:
        """调度文件索引"""
        if not self.storage_manager:
            return
        try:
            sm = self.storage_manager
            # 查找该文件是否已入库
            import hashlib
            h = hashlib.md5()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            checksum = h.hexdigest()

            item = sm.db.get_item_by_checksum(checksum)
            if item and item["embedding_status"] == "done":
                logger.debug(f"索引跳过（已存在且已索引）: {path}")
                return

            if item:
                # 已入库但未索引 → 触发索引
                sm.index_item(item["id"])
                self.stats["files_indexed"] += 1
            else:
                # 未入库 → 先入库再索引
                item_id = sm.ingest_file(path)
                if item_id:
                    sm.index_item(item_id)
                    self.stats["files_indexed"] += 1

        except Exception as e:
            self.stats["index_errors"] += 1
            logger.warning(f"watchdog 索引失败: {path} — {e}")

    def _cleanup_deleted(self, path: str) -> None:
        """文件删除时清理索引"""
        if not self.storage_manager:
            return
        try:
            sm = self.storage_manager
            # 查询 repo_path 匹配的记录
            all_items = sm.db.list_items(limit=100000)
            filename = Path(path).name
            for item in all_items:
                if filename in (item.get("repo_path", "") or ""):
                    # 删除 ChromaDB 索引
                    if sm.chroma:
                        sm.chroma.delete_item(item["id"])
                    sm.db.update_embedding_status(item["id"], "pending")
                    logger.info(f"已清理索引: {item['id'][:8]} ({filename})")
        except Exception as e:
            logger.warning(f"清理索引失败: {path} — {e}")

    # ── 全量扫描 ──────────────────────────────────

    def full_scan(self) -> dict:
        """全量扫描仓库，补齐所有未索引项。返回扫描统计"""
        logger.info("开始全量扫描仓库...")
        stats = {"total": 0, "indexed": 0, "skipped": 0, "errors": 0}

        files_dir = Path(self.watch_dir) / "files"
        if not files_dir.exists():
            logger.info("files 目录不存在，跳过扫描")
            return stats

        for file_path in files_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if self._handler and self._handler._should_skip(str(file_path)):
                continue
            stats["total"] += 1

            try:
                # 检查是否已在 DB 中且已索引
                if self.storage_manager:
                    import hashlib
                    h = hashlib.md5()
                    with open(str(file_path), "rb") as f:
                        for chunk in iter(lambda: f.read(65536), b""):
                            h.update(chunk)
                    checksum = h.hexdigest()
                    item = self.storage_manager.db.get_item_by_checksum(checksum)

                    if item and item["embedding_status"] == "done":
                        stats["skipped"] += 1
                        continue

                    # 入库 + 索引
                    item_id = item["id"] if item else self.storage_manager.ingest_file(str(file_path))
                    if item_id and self.storage_manager.index_item(item_id):
                        stats["indexed"] += 1
                    else:
                        stats["errors"] += 1
                else:
                    stats["skipped"] += 1

            except Exception as e:
                stats["errors"] += 1
                logger.debug(f"扫描跳过: {file_path} — {e}")

        logger.info(
            f"全量扫描完成: {stats['total']} 文件, "
            f"索引 {stats['indexed']}, 跳过 {stats['skipped']}, 错误 {stats['errors']}"
        )
        return stats


# ── Qt 信号封装（GUI 环境下使用）───────────────────

if _HAS_QT:
    class FileWatcherQt(FileWatcher, QObject):
        """带 Qt 信号的 FileWatcher，用于 UI 进度反馈"""

        scan_progress = Signal(int, int)        # (current, total)
        scan_done = Signal(dict)                # stats dict
        file_indexed = Signal(str)              # file_path
        index_error = Signal(str, str)          # (file_path, error)

        def __init__(self, watch_dir: str, storage_manager=None):
            QObject.__init__(self)
            FileWatcher.__init__(self, watch_dir, storage_manager)

        def full_scan(self) -> dict:
            self.scan_progress.emit(0, 0)
            stats = super().full_scan()
            self.scan_done.emit(stats)
            return stats

        def _on_new_file(self, path: str) -> None:
            super()._on_new_file(path)
            self.file_indexed.emit(path)

        def _schedule_index(self, path: str, reason: str = "") -> None:
            try:
                super()._schedule_index(path, reason)
            except Exception as e:
                self.index_error.emit(path, str(e))
else:
    FileWatcherQt = FileWatcher
