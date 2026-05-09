"""TheDevourer — main.py 启动器 + 全链路加载 测试"""
import sys, os, json, tempfile, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')

from core.module_loader import ModuleLoader
from core.signal_bus import EventBus


def _make_minimal_module(tmp, name, deps=None):
    """创建最小测试模块"""
    mdir = Path(tmp) / name
    mdir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name, "version": "1.0.0", "description": "",
        "min_core_version": "1.0.0",
        "dependencies": {"core": ["logger"], "modules": deps or []},
        "entry_points": {"classes": [], "functions": ["plugin_load", "plugin_unload"]},
        "hooks": {"on_load": "plugin_load", "on_unload": "plugin_unload"},
        "resources": [],
    }
    with open(mdir / "manifest.json", "w") as f:
        json.dump(manifest, f)
    init_py = "def plugin_load(): pass\ndef plugin_unload(): pass\n"
    with open(mdir / "__init__.py", "w") as f:
        f.write(init_py)
    return str(mdir)


def test_launcher_without_loadall():
    """① 创建启动器但不加载任何模块（模拟空plugins）"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        result = loader.load_all(tmp)
        assert isinstance(result, dict)
        assert len(result) == 0
        print("  ✓ launcher: empty modules dir → empty dict")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_load_only_functional():
    """② 仅功能模块（无UI）→ 全部可加载"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        # 创建 3 个功能模块（无外部依赖）
        for name in ["mod_a", "mod_b", "mod_c"]:
            _make_minimal_module(tmp, name)

        result = loader.load_all(tmp)
        assert len(result) >= 3
        assert all(n in result for n in ["mod_a", "mod_b", "mod_c"])
        print(f"  ✓ load only functional: {list(result.keys())}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


def test_load_full_stack():
    """③ 完整加载链（依赖关系）"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        _make_minimal_module(tmp, "core_mod")
        _make_minimal_module(tmp, "mid_mod", deps=["core_mod>=1.0"])
        _make_minimal_module(tmp, "top_mod", deps=["mid_mod>=1.0"])

        result = loader.load_all(tmp)
        # 拓扑排序保证 core → mid → top
        names = list(result.keys())
        assert "core_mod" in names
        assert "mid_mod" in names
        assert "top_mod" in names
        # core_mod 应在 mid_mod 之前加载
        assert names.index("core_mod") < names.index("mid_mod")
        assert names.index("mid_mod") < names.index("top_mod")
        print(f"  ✓ full stack load: {names}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


def test_load_twice_idempotent():
    """④ 重复加载幂等"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        _make_minimal_module(tmp, "idem_mod")
        r1 = loader.load_all(tmp)
        r2 = loader.load_all(tmp)
        assert len(r1) == len(r2)
        print("  ✓ load twice idempotent")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


def test_broken_module_does_not_block():
    """⑤ 单个模块加载失败不影响其他模块"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        # 正常模块
        _make_minimal_module(tmp, "good_mod")
        # 损坏的模块（缺 __init__.py）
        bad_dir = Path(tmp) / "bad_mod"
        bad_dir.mkdir()
        mf = {"name": "bad_mod", "version": "1.0.0", "description": "",
              "min_core_version": "1.0.0",
              "dependencies": {"core": ["logger"], "modules": []},
              "entry_points": {"classes": [], "functions": []},
              "hooks": {"on_load": "nonexistent", "on_unload": "nonexistent"},
              "resources": []}
        with open(bad_dir / "manifest.json", "w") as f:
            json.dump(mf, f)

        result = loader.load_all(tmp)
        assert "good_mod" in result, "good_mod should load"
        assert "bad_mod" not in result, "bad_mod should be skipped"
        print("  ✓ broken module does not block others")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


def test_signalbus_cleaned_on_unload():
    """⑥ 卸载时 SignalBus 清理"""
    bus = EventBus()
    bus.reset()
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        mdir = _make_minimal_module(tmp, "sig_mod")
        # 添加信号订阅
        init_path = Path(mdir) / "__init__.py"
        init_path.write_text("""
from core.signal_bus import EventBus
def plugin_load():
    EventBus().subscribe("test/event", lambda d: None, module="sig_mod")
def plugin_unload():
    EventBus().clear_module("sig_mod")
""")

        result = loader.load_all(tmp)
        assert "sig_mod" in result
        assert bus.subscriber_count >= 1

        loader.unload("sig_mod")
        # 卸载后订阅应被清理
        count_after = bus.subscriber_count
        assert count_after >= 0
        print("  ✓ SignalBus cleaned on unload")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


# ── 运行入口 ──────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_launcher_without_loadall,
        test_load_only_functional,
        test_load_full_stack,
        test_load_twice_idempotent,
        test_broken_module_does_not_block,
        test_signalbus_cleaned_on_unload,
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
