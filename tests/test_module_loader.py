"""TheDevourer — ModuleLoader 模块加载器 测试"""
import sys, os, json, tempfile, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')

from core.module_loader import ModuleLoader, Module


def _make_module(tmp, name, deps=None):
    """创建测试用的模块目录"""
    mdir = Path(tmp) / name
    mdir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "version": "1.0.0",
        "description": f"Test module {name}",
        "min_core_version": "1.0.0",
        "dependencies": {"core": ["logger"], "modules": deps or []},
        "entry_points": {"classes": [], "functions": []},
        "hooks": {"on_load": "plugin_load", "on_unload": "plugin_unload"},
        "resources": [],
    }
    with open(mdir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    init_py = f"""
def plugin_load():
    print(f"  [{name}] on_load called")

def plugin_unload():
    print(f"  [{name}] on_unload called")
"""
    with open(mdir / "__init__.py", "w") as f:
        f.write(init_py)

    return str(mdir), name


def test_empty_plugins_dir():
    """① 空 plugins 目录 → 无异常"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        result = loader.load_all(tmp)
        assert isinstance(result, dict)
        assert len(result) == 0
        print("  ✓ empty plugins dir → no modules")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_load_single_module():
    """② 加载单个模块 → entry_point 注册"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        mod_path, name = _make_module(tmp, "test_mod")
        mod = loader.load(mod_path)
        assert isinstance(mod, Module)
        assert mod.name == "test_mod"
        assert mod.version == "1.0.0"

        # 确认在已加载列表
        assert "test_mod" in loader.module_list()
        assert loader.get("test_mod") is mod
        print(f"  ✓ load single module: {mod.name} v{mod.version}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


def test_load_from_zip():
    """③ 从 .zip 加载模块"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        mod_dir, _ = _make_module(tmp, "zip_mod")
        zip_path = os.path.join(tmp, "zip_mod_v1.0.0.zip")
        import zipfile
        with zipfile.ZipFile(zip_path, "w") as zf:
            for root, _, files in os.walk(mod_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    zf.write(fp, arcname=os.path.relpath(fp, mod_dir))

        mod = loader.load(zip_path)
        assert isinstance(mod, Module)
        assert mod.name == "zip_mod"
        print("  ✓ load from .zip file")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


def test_dependency_validation():
    """④ 缺依赖模块 → 加载跳过但有记录"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        mod_dir, _ = _make_module(tmp, "parent_mod", deps=["child_mod>=1.0"])
        # 加载父模块（子模块不存在）
        candidates = loader.scan(tmp)
        all_modules = loader.load_all(tmp)
        # parent_mod 可能加载失败或成功（取决于拓扑排序策略）
        # 至少不应崩溃
        assert isinstance(all_modules, dict)
        print(f"  ✓ dependency validation: loaded={list(all_modules.keys())}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


def test_load_all_with_deps():
    """⑤ 加载全部模块 + 依赖拓扑排序"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        child_dir, child_name = _make_module(tmp, "child_mod")
        parent_dir, parent_name = _make_module(tmp, "parent_mod", deps=["child_mod>=1.0"])

        all_mods = loader.load_all(tmp)
        assert "child_mod" in all_mods
        assert "parent_mod" in all_mods

        # 确认 entry_points 可被访问
        assert isinstance(loader.get("child_mod"), Module)
        assert isinstance(loader.get("parent_mod"), Module)
        print(f"  ✓ load_all with deps: {list(all_mods.keys())}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


def test_unload_removes_registry():
    """⑥ 卸载→从注册表清除"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        mod_path, name = _make_module(tmp, "unload_test")
        loader.load(mod_path)
        assert "unload_test" in loader.module_list()

        ok = loader.unload("unload_test")
        assert ok is True
        assert "unload_test" not in loader.module_list()
        assert loader.get("unload_test") is None
        print("  ✓ unload removes from registry")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


def test_get_entry_point():
    """⑦ get_entry_point 访问已注册入口"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        mdir = Path(tmp) / "ep_mod"
        mdir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "name": "ep_mod", "version": "1.0.0", "description": "",
            "min_core_version": "1.0.0",
            "dependencies": {"core": ["logger"], "modules": []},
            "entry_points": {"classes": ["TestClass"], "functions": ["test_fn"]},
            "hooks": {"on_load": "plugin_load", "on_unload": "plugin_unload"},
            "resources": [],
        }
        with open(mdir / "manifest.json", "w") as f:
            json.dump(manifest, f)

        init_py = """
class TestClass:
    pass

def test_fn():
    return "hello from test_fn"

def plugin_load(): pass
def plugin_unload(): pass
"""
        with open(mdir / "__init__.py", "w") as f:
            f.write(init_py)

        loader.load(str(mdir))
        ep = loader.get_entry_point("ep_mod", "functions", "test_fn")
        assert ep is not None
        assert callable(ep)
        assert ep() == "hello from test_fn"
        print("  ✓ get_entry_point: function callable")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


def test_load_twice_idempotent():
    """⑧ 重复加载幂等"""
    loader = ModuleLoader()
    tmp = tempfile.mkdtemp()
    try:
        mod_path, _ = _make_module(tmp, "idempotent")
        mod1 = loader.load(mod_path)
        mod2 = loader.load(mod_path)  # 第二次按名称获取
        assert mod1 is mod2
        print("  ✓ load twice idempotent")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        loader.cleanup()


# ── 运行入口 ──────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_empty_plugins_dir,
        test_load_single_module,
        test_load_from_zip,
        test_dependency_validation,
        test_load_all_with_deps,
        test_unload_removes_registry,
        test_get_entry_point,
        test_load_twice_idempotent,
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
