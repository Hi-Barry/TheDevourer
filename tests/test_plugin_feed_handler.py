"""TheDevourer — feed_handler 插件模块 测试"""
import sys, os, json, tempfile, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')

from core.module_loader import ModuleLoader
from core.signal_bus import EventBus


def _mod_path():
    """返回 feed_handler 模块目录"""
    return str(Path(__file__).resolve().parent.parent / "modules" / "feed_handler")


def test_load_module():
    """① ModuleLoader 加载 feed_handler 模块"""
    loader = ModuleLoader()
    try:
        mod = loader.load(_mod_path())
        assert mod is not None
        assert mod.name == "feed_handler"
        assert mod.version == "1.0.0"
        print(f"  ✓ Module loaded: {mod.name} v{mod.version}")
    finally:
        loader.cleanup()


def test_entry_points_registered():
    """② 入口点全部注册"""
    loader = ModuleLoader()
    try:
        mod = loader.load(_mod_path())
        assert "classes.FeedItem" in mod.entry_points
        assert "classes.FeedSourceType" in mod.entry_points
        assert "classes.FeedQueueWorker" in mod.entry_points
        assert "functions.extract_urls" in mod.entry_points
        assert "functions.is_url" in mod.entry_points
        assert "functions.compute_md5" in mod.entry_points
        assert "functions.parse_mime_data" in mod.entry_points
        print(f"  ✓ {len(mod.entry_points)} entry points registered")
    finally:
        loader.cleanup()


def test_feed_item_creation():
    """③ FeedItem 创建和 display_name"""
    loader = ModuleLoader()
    try:
        mod = loader.load(_mod_path())
        FeedItem = mod.entry_points["classes.FeedItem"]
        FeedSourceType = mod.entry_points["classes.FeedSourceType"]

        item = FeedItem(source_type=FeedSourceType.FILE, file_paths=["/tmp/test.py"])
        assert item.id is not None
        assert "test.py" in item.display_name
        assert item.is_file_type is True
        assert item.is_url_type is False
        print("  ✓ FeedItem creation + properties")
    finally:
        loader.cleanup()


def test_url_functions():
    """④ URL 提取和判断函数"""
    loader = ModuleLoader()
    try:
        mod = loader.load(_mod_path())
        extract_urls = mod.entry_points["functions.extract_urls"]
        is_url = mod.entry_points["functions.is_url"]

        urls = extract_urls("看 https://github.com/repo 和 https://arxiv.org/paper")
        assert len(urls) == 2
        assert "github.com" in urls[0]

        assert is_url("https://example.com") is True
        assert is_url("普通文本") is False
        print("  ✓ URL functions: extract + is_url")
    finally:
        loader.cleanup()


def test_plugin_hooks():
    """⑤ 插件 hook 存在且可调用"""
    loader = ModuleLoader()
    try:
        mod = loader.load(_mod_path())
        assert hasattr(mod.instance, "plugin_load")
        assert hasattr(mod.instance, "plugin_unload")
        assert callable(getattr(mod.instance, "plugin_load"))
        assert callable(getattr(mod.instance, "plugin_unload"))
        print("  ✓ plugin hooks: plugin_load + plugin_unload")
    finally:
        loader.cleanup()


def test_signal_bus_subscription():
    """⑥ 加载后 SignalBus 有订阅"""
    bus = EventBus()
    bus.reset()
    loader = ModuleLoader()
    try:
        mod = loader.load(_mod_path())
        count_before = bus.subscriber_count
        assert count_before >= 1, f"Expected ≥1 subscriber, got {count_before}"
        print(f"  ✓ SignalBus subscriptions: {count_before}")
    finally:
        bus.clear_module("feed_handler")
        loader.cleanup()


def test_unload_cleans_signal():
    """⑦ 卸载后 SignalBus 清理"""
    bus = EventBus()
    bus.reset()
    loader = ModuleLoader()
    try:
        loader.load(_mod_path())
        assert bus.subscriber_count >= 1
        loader.unload("feed_handler")
        # 卸载后相关订阅应被清理
        assert "feed_handler" not in loader._loaded
        print("  ✓ unload cleans SignalBus subscriptions")
    finally:
        loader.cleanup()


# ── 运行入口 ──────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_load_module,
        test_entry_points_registered,
        test_feed_item_creation,
        test_url_functions,
        test_plugin_hooks,
        test_signal_bus_subscription,
        test_unload_cleans_signal,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            import traceback
            print(f"  ✗ {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{'='*40}\n结果: {passed}/{len(tests)} 通过")
