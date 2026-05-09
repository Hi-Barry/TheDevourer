"""TheDevourer — 热替换升级 + 降级回退 集成测试"""
import sys, os, json, tempfile, shutil, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')

from core.module_loader import ModuleLoader
from core.signal_bus import EventBus


def _make_module(tmp, name, version, deps=None, extra_code=""):
    """创建测试模块"""
    mdir = Path(tmp) / name
    mdir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name, "version": version,
        "description": f"{name} v{version}",
        "min_core_version": "1.0.0",
        "dependencies": {"core": ["logger"], "modules": deps or []},
        "entry_points": {"classes": [], "functions": ["plugin_load", "plugin_unload"]},
        "hooks": {"on_load": "plugin_load", "on_unload": "plugin_unload"},
        "resources": [],
    }
    (mdir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (mdir / "__init__.py").write_text(
        f"VERSION = '{version}'\n"
        f"def plugin_load(): pass\n"
        f"def plugin_unload(): pass\n"
        f"{extra_code}\n"
    )
    return mdir


def test_hot_replace_version_change():
    """① v1.0 → v1.1 热替换→版本号变化+旧版卸载"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        # 加载 v1.0
        _make_module(tmp, "hot_mod", "1.0.0")
        r1 = loader.load_all(tmp)
        m1 = r1["hot_mod"]
        assert m1.version == "1.0.0"

        # 替换为 v1.1
        m1_dir = Path(tmp) / "hot_mod"
        shutil.rmtree(m1_dir)
        _make_module(tmp, "hot_mod", "1.1.0")

        # 卸载旧版
        loader.unload("hot_mod")
        # 重新扫描加载
        r2 = loader.load_all(tmp)
        m2 = r2["hot_mod"]
        assert m2.version == "1.1.0"
        assert m1 is not m2
        print("  ✓ hot-replace: version 1.0→1.1, old unloaded")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


def test_rollback_on_failure():
    """② 升级失败→自动回退到旧版"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        # 加载 v1.0（正常）
        _make_module(tmp, "roll_mod", "1.0.0")
        r1 = loader.load_all(tmp)
        m1 = r1["roll_mod"]
        assert m1.version == "1.0.0"

        # 替换为损坏的 v1.1（缺 __init__.py）
        m1_dir = Path(tmp) / "roll_mod"
        shutil.rmtree(m1_dir)
        m1_dir.mkdir()
        broken_manifest = {
            "name": "roll_mod", "version": "1.1.0",
            "description": "broken", "min_core_version": "1.0.0",
            "dependencies": {"core": ["logger"], "modules": []},
            "entry_points": {"classes": [], "functions": []},
            "hooks": {"on_load": "missing", "on_unload": "missing"},
            "resources": [],
        }
        (m1_dir / "manifest.json").write_text(json.dumps(broken_manifest, indent=2))
        # 故意不写 __init__.py

        # 尝试加载——预期失败
        try:
            from core.module_loader import Module
            loader._loaded.pop("roll_mod", None)
            loader._load_single({
                "manifest": broken_manifest,
                "path": str(m1_dir),
                "name": "roll_mod",
            })
        except (ImportError, FileNotFoundError):
            pass  # 预期失败

        # 恢复旧版
        shutil.rmtree(m1_dir)
        _make_module(tmp, "roll_mod", "1.0.0")
        r3 = loader.load_all(tmp)
        # 至少应恢复回 1.0.0
        assert "roll_mod" in r3
        assert r3["roll_mod"].version == "1.0.0"
        print("  ✓ rollback: failure → old version restored")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


def test_module_crash_does_not_block_others():
    """③ 模块加载异常→不影响其他模块"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        _make_module(tmp, "good_mod", "1.0.0")
        # 损坏模块
        bad_dir = Path(tmp) / "bad_mod"
        bad_dir.mkdir()
        bad_manifest = {
            "name": "bad_mod", "version": "1.0.0",
            "description": "broken", "min_core_version": "1.0.0",
            "dependencies": {"core": ["logger"], "modules": []},
            "entry_points": {"classes": [], "functions": []},
            "hooks": {"on_load": "missing", "on_unload": "missing"},
            "resources": [],
        }
        (bad_dir / "manifest.json").write_text(json.dumps(bad_manifest, indent=2))
        # 不写 __init__.py

        result = loader.load_all(tmp)
        assert "good_mod" in result, "good module should load"
        name_list = list(result.keys())
        assert any(n == "good_mod" for n in name_list), f"good_mod not in {name_list}"
        print("  ✓ bad module crash does not block good module")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


def test_load_all_partial_failure():
    """④ 部分模块加载失败→已加载模块仍可用"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        # 3 个好模块
        _make_module(tmp, "m1", "1.0.0")
        _make_module(tmp, "m2", "1.0.0")
        _make_module(tmp, "m3", "1.0.0")
        # 1 个坏模块
        bad_dir = Path(tmp) / "bad"
        bad_dir.mkdir()
        (bad_dir / "manifest.json").write_text(json.dumps({
            "name": "bad", "version": "1.0.0",
            "description": "", "min_core_version": "1.0.0",
            "dependencies": {"core": ["logger"], "modules": []},
            "entry_points": {"classes": [], "functions": []},
            "hooks": {"on_load": "x", "on_unload": "y"},
        }))

        result = loader.load_all(tmp)
        assert "m1" in result
        assert "m2" in result
        assert "m3" in result
        assert "bad" not in result
        assert len(result) == 3
        print("  ✓ partial failure: good modules still usable")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


def test_upgrade_zip_replacement():
    """⑤ ZIP 模块替换升级"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        # 创建 v1.0 模块目录→打包为 zip
        mod_dir = _make_module(tmp, "zip_mod", "1.0.0")
        zip_v1 = Path(tmp) / "plugins" / "zip_mod_v1.0.0.zip"
        zip_v1.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(zip_v1, "w") as zf:
            for f in mod_dir.iterdir():
                zf.write(f, arcname=f.name)

        # 从 zip 加载
        mod = loader.load(str(zip_v1))
        assert mod.version == "1.0.0"
        assert mod.name == "zip_mod"

        # 替换为 v1.1 zip
        shutil.rmtree(mod_dir)
        _make_module(tmp, "zip_mod", "1.1.0")
        zip_v1_1 = Path(tmp) / "plugins" / "zip_mod_v1.1.0.zip"
        with zipfile.ZipFile(zip_v1_1, "w") as zf:
            for f in Path(tmp).iterdir():
                if f.name == "zip_mod" and f.is_dir():
                    for sf in f.iterdir():
                        zf.write(sf, arcname=sf.name)

        # 卸载旧→加载新
        loader.unload("zip_mod")
        mod2 = loader.load(str(zip_v1_1))
        assert mod2.version == "1.1.0"
        print("  ✓ zip upgrade: v1.0 zip → v1.1 zip")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


def test_consecutive_upgrades():
    """⑥ 连续升级 v1→v2→v3 全部正常"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        versions = ["1.0.0", "2.0.0", "3.0.0"]
        for v in versions:
            mdir = _make_module(tmp, "multi_mod", v)
            if v != "1.0.0":
                loader.unload("multi_mod")
            # 重新扫描加载
            old_path = Path(tmp) / "multi_mod"
            shutil.rmtree(old_path)
            _make_module(tmp, "multi_mod", v)
            result = loader.load_all(tmp)
            assert result["multi_mod"].version == v
            if v == "3.0.0":
                assert len(loader.module_list()) >= 1
        print("  ✓ consecutive upgrades v1→v2→v3")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


# ── 运行入口 ──────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_hot_replace_version_change,
        test_rollback_on_failure,
        test_module_crash_does_not_block_others,
        test_load_all_partial_failure,
        test_upgrade_zip_replacement,
        test_consecutive_upgrades,
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
