"""TheDevourer — manifest.json 格式校验 测试"""
import sys, json, tempfile, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')

from core.manifest_validator import (
    validate_manifest, validate_manifest_file, ValidationResult,
)


def valid_manifest() -> dict:
    return {
        "name": "feed_handler",
        "version": "1.0.0",
        "description": "测试模块",
        "min_core_version": "1.0.0",
        "dependencies": {"core": ["logger", "signal_bus"], "modules": []},
        "entry_points": {"classes": ["FeedItem"], "functions": ["is_url"]},
        "hooks": {"on_load": "plugin_load", "on_unload": "plugin_unload"},
        "resources": [],
    }


def test_valid_manifest_passes():
    """① 合法 manifest → 通过"""
    result = validate_manifest(valid_manifest())
    assert result.is_valid, f"Expected valid, got errors: {result.errors}"
    assert len(result.warnings) == 0, f"Unexpected warnings: {result.warnings}"
    print("  ✓ valid manifest passes")


def test_missing_required_field():
    """② 缺必填字段 → 报错"""
    manifest = valid_manifest()
    del manifest["version"]
    result = validate_manifest(manifest)
    assert not result.is_valid
    assert any("version" in e for e in result.errors)
    print("  ✓ missing required field → error")


def test_invalid_semver():
    """③ 版本号格式错误 → 报错"""
    manifest = valid_manifest()
    manifest["version"] = "1.0"
    result = validate_manifest(manifest)
    assert not result.is_valid
    assert any("版本号" in e for e in result.errors)

    manifest["version"] = "abc"
    result = validate_manifest(manifest)
    assert not result.is_valid
    print("  ✓ invalid semver → error")


def test_invalid_module_name():
    """④ 模块名格式错误 → 报错"""
    manifest = valid_manifest()
    manifest["name"] = "MyModule"
    result = validate_manifest(manifest)
    assert not result.is_valid
    assert any("模块名" in e for e in result.errors)

    manifest["name"] = "123module"
    result = validate_manifest(manifest)
    assert not result.is_valid
    print("  ✓ invalid module name → error")


def test_missing_hooks():
    """⑤ hooks 缺必填项 → 报错"""
    manifest = valid_manifest()
    del manifest["hooks"]["on_load"]
    result = validate_manifest(manifest)
    assert not result.is_valid
    assert any("on_load" in e for e in result.errors)
    print("  ✓ missing hooks → error")


def test_dependencies_format():
    """⑥ dependencies 格式校验"""
    manifest = valid_manifest()
    manifest["dependencies"] = "not a dict"
    result = validate_manifest(manifest)
    assert not result.is_valid
    assert any("dependencies" in e for e in result.errors)

    manifest["dependencies"] = {"core": "not a list", "modules": []}
    result = validate_manifest(manifest)
    assert not result.is_valid
    print("  ✓ dependencies format check")


def test_entry_point_duplicate_warning():
    """⑦ entry_point 重复 → 警告"""
    manifest = valid_manifest()
    manifest["entry_points"] = {
        "classes": ["FeedItem", "FeedItem"],
        "functions": [],
    }
    result = validate_manifest(manifest)
    assert result.is_valid  # 重复不会导致失败
    assert len(result.warnings) >= 1
    assert any("重复" in w for w in result.warnings)
    print("  ✓ duplicate entry_point → warning")


def test_validate_manifest_file():
    """⑧ validate_manifest_file 从文件读取"""
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "manifest.json")
        with open(path, "w") as f:
            json.dump(valid_manifest(), f)

        result = validate_manifest_file(path)
        assert result.is_valid

        # 不存在的文件
        result = validate_manifest_file(tmp + "/nonexistent.json")
        assert not result.is_valid
        assert any("不存在" in e for e in result.errors)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    print("  ✓ validate_manifest_file reads + handles missing")


def test_12_real_manifest_files():
    """⑨ 校验全部 12 个实际 manifest.json"""
    modules_dir = Path(__file__).resolve().parent.parent / "modules"
    count = 0
    for mdir in sorted(modules_dir.iterdir()):
        mjson = mdir / "manifest.json"
        if mjson.exists():
            result = validate_manifest_file(str(mjson))
            assert result.is_valid, f"{mjson} failed: {result.errors}"
            count += 1
    assert count == 12, f"Expected 12 manifests, found {count}"
    print(f"  ✓ all {count} real manifest files pass validation")


def test_resources_not_list():
    """⑩ resources 不是列表 → 报错"""
    manifest = valid_manifest()
    manifest["resources"] = "not a list"
    result = validate_manifest(manifest)
    assert not result.is_valid
    assert any("resources" in e for e in result.errors)
    print("  ✓ resources not list → error")


# ── 运行入口 ──────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_valid_manifest_passes,
        test_missing_required_field,
        test_invalid_semver,
        test_invalid_module_name,
        test_missing_hooks,
        test_dependencies_format,
        test_entry_point_duplicate_warning,
        test_validate_manifest_file,
        test_12_real_manifest_files,
        test_resources_not_list,
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
