"""大嘴怪 — FileWatcher 文件监听 测试"""
import sys, os, tempfile, shutil, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')

from core.file_watcher import FileWatcher, RepoWatcherHandler
from core.db import Database

# 尝试导入 watchdog
try:
    from watchdog.observers import Observer
    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False


def setup():
    """创建测试环境"""
    tmp = tempfile.mkdtemp()
    files_dir = os.path.join(tmp, "files")
    os.makedirs(files_dir, exist_ok=True)

    db = Database(os.path.join(tmp, "test.db"))
    db.init_schema()

    class MockConfig:
        repo_path = tmp
        files_path = files_dir
        chroma_path = os.path.join(tmp, "chroma_db")
        embedding_model = "all-MiniLM-L6-v2"
        def ensure_paths(self): pass

    config = MockConfig()
    return tmp, files_dir, db, config


def test_should_skip():
    """⑥ _should_skip 跳过规则"""
    handler = RepoWatcherHandler()

    # 隐藏文件
    assert handler._should_skip("/tmp/.hidden.txt") is True
    # 临时文件
    assert handler._should_skip("/tmp/test.tmp") is True
    assert handler._should_skip("/tmp/test.swp") is True
    # 数据库文件
    assert handler._should_skip("/tmp/big_mouth.db") is True
    assert handler._should_skip("/tmp/big_mouth.db-wal") is True
    # chroma_db 目录
    assert handler._should_skip("/tmp/chroma_db/something.sqlite3") is True
    # 正常文件 → 不跳过
    assert handler._should_skip("/tmp/files/notes.txt") is False
    assert handler._should_skip("/tmp/test.py") is False

    print(f"  ✓ _should_skip: {6} rules OK")


def test_debounce_check():
    """⑤ _debounce_check 防抖"""
    handler = RepoWatcherHandler()

    # 第一次 → 通过
    assert handler._debounce_check("/tmp/test.txt", cooldown=2.0) is True
    # 第二次（2 秒内）→ 跳过
    assert handler._debounce_check("/tmp/test.txt", cooldown=2.0) is False

    # 不同文件 → 通过
    assert handler._debounce_check("/tmp/other.txt", cooldown=2.0) is True

    print("  ✓ _debounce_check: same file blocked, different file allowed")


def test_full_scan_empty():
    """④ full_scan 空目录 → 统计为 0"""
    tmp, files_dir, db, config = setup()
    try:
        fw = FileWatcher(files_dir, None)
        fw.config = config

        stats = fw.full_scan()
        assert stats["total"] == 0
        assert stats["indexed"] == 0
        assert stats["errors"] == 0

        print("  ✓ full_scan: empty dir → 0 stats")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_full_scan_with_files():
    """④ full_scan 含文件时统计正确"""
    tmp, files_dir, db, config = setup()
    try:
        # 在 files/ 子目录下创建测试文件（full_scan 遍历 {watch_dir}/files/）
        files_sub = Path(tmp) / "files"
        files_sub.mkdir(parents=True, exist_ok=True)
        (files_sub / "a.txt").write_text("content a")
        (files_sub / "b.md").write_text("content b")
        (files_sub / ".hidden.py").write_text("hidden")  # 应被跳过

        from core.storage_manager import StorageManager
        sm = StorageManager(db, None)
        sm.config = config

        fw = FileWatcher(tmp, sm)
        fw.config = config

        stats = fw.full_scan()
        # 至少发现 2 个非隐藏文件（a.txt, b.md）
        assert stats["total"] >= 2, f"Expected ≥2 files found, got {stats}"

        print(f"  ✓ full_scan: with files → {stats}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_start_stop_lifecycle():
    """⑦ start/stop 生命周期"""
    tmp, files_dir, db, config = setup()
    try:
        fw = FileWatcher(files_dir, None)
        try:
            fw.start()
            assert fw._running is True
            assert fw._observer is not None
            time.sleep(0.3)
            fw.start()  # 重复 start 不报错
            fw.stop()
            assert fw._running is False
            print("  ✓ start/stop lifecycle OK")
        except OSError as e:
            if "inotify" in str(e):
                print("  ⚠ start/stop lifecycle: skipped (inotify limit)")
            else:
                raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_on_new_file():
    """① 创建文件 → _on_new_file 触发入库"""
    tmp, files_dir, db, config = setup()
    try:
        from core.storage_manager import StorageManager
        sm = StorageManager(db, None)
        sm.config = config

        fw = FileWatcher(files_dir, sm)
        fw.config = config

        # 直接调用 _on_new_file（模拟事件）
        new_path = os.path.join(files_dir, "new_note.txt")
        with open(new_path, "w") as f:
            f.write("New file content with Python and Docker")
        fw._on_new_file(new_path)
        time.sleep(0.5)

        # 文件应已入库
        stats = db.get_stats()
        assert stats["total_items"] >= 1, f"Expected ≥1 item, got {stats}"

        print("  ✓ on_new_file → ingest triggered")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_on_file_modified():
    """② 修改文件 → _on_file_modified"""
    tmp, files_dir, db, config = setup()
    try:
        from core.storage_manager import StorageManager
        sm = StorageManager(db, None)
        sm.config = config

        fw = FileWatcher(files_dir, sm)
        fw.config = config

        # 先创建一个已入库的文件
        path = os.path.join(files_dir, "mod_test.txt")
        with open(path, "w") as f:
            f.write("original")
        fw._on_new_file(path)

        # 修改
        time.sleep(0.2)
        with open(path, "w") as f:
            f.write("modified content with more text")
        fw._on_file_modified(path)

        # 不应抛出异常即为成功
        print("  ✓ on_file_modified → no exception")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_on_file_deleted():
    """③ 删除文件 → _on_file_deleted"""
    tmp, files_dir, db, config = setup()
    try:
        from core.storage_manager import StorageManager
        sm = StorageManager(db, None)
        sm.config = config

        fw = FileWatcher(files_dir, sm)
        fw.config = config

        # 先入库再删除
        path = os.path.join(files_dir, "del_test.txt")
        with open(path, "w") as f:
            f.write("delete test")
        fw._on_new_file(path)
        time.sleep(0.2)

        os.remove(path)
        fw._on_file_deleted(path)

        # 不应抛出异常即为成功
        print("  ✓ on_file_deleted → no exception")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── 运行入口 ──────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_should_skip,
        test_debounce_check,
        test_full_scan_empty,
        test_full_scan_with_files,
        test_start_stop_lifecycle,
        test_on_new_file,
        test_on_file_modified,
        test_on_file_deleted,
    ]

    watchdog_note = f"watchdog: {'✓' if _WATCHDOG_AVAILABLE else '✗ (mock/直接调用模式)'}"
    print(f"  环境: {watchdog_note}")

    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            import traceback
            print(f"  ✗ {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{'='*40}\n结果: {passed}/{len(tests)} 通过 (watchdog: {'真实' if _WATCHDOG_AVAILABLE else 'mock'})")
