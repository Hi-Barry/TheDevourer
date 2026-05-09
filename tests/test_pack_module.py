"""TheDevourer — pack_module.py 模块打包 测试"""
import sys, os, json, tempfile, shutil, zipfile, hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')


def _make_test_module(tmp, name="test_mod", version="1.0.0", with_init=True):
    """创建测试模块目录"""
    mdir = Path(tmp) / name
    mdir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name, "version": version, "description": "",
        "min_core_version": "1.0.0",
        "dependencies": {"core": ["logger"], "modules": []},
        "entry_points": {"classes": [], "functions": ["plugin_load", "plugin_unload"]},
        "hooks": {"on_load": "plugin_load", "on_unload": "plugin_unload"},
        "resources": [],
    }
    (mdir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    if with_init:
        (mdir / "__init__.py").write_text("def plugin_load(): pass\ndef plugin_unload(): pass\n")
    return mdir


def test_pack_single_module():
    """① 打包单模块→zip 存在+内容正确"""
    from tools.pack_module import pack_module
    tmp = tempfile.mkdtemp()
    out = Path(tmp) / "outputs"
    try:
        _make_test_module(tmp)
        result = pack_module("test_mod", source_dir=str(Path(tmp) / "test_mod"), output_dir=str(out))
        zip_path = Path(result["zip_path"])
        assert zip_path.exists(), f"zip not found: {zip_path}"
        assert result["name"] == "test_mod"
        assert result["version"] == "1.0.0"
        assert result["file_count"] >= 2  # manifest.json + __init__.py
        assert result["sha256"] != ""
        assert result["size_bytes"] > 0

        # zip 内容可读取
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "manifest.json" in names
            assert "__init__.py" in names
            manifest_content = json.loads(zf.read("manifest.json"))
            assert manifest_content["name"] == "test_mod"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("  ✓ pack single module → zip valid + manifest readable")


def test_pack_outputs_sha256():
    """② 打包产物含 .sha256 校验文件"""
    from tools.pack_module import pack_module
    tmp = tempfile.mkdtemp()
    out = Path(tmp) / "outputs"
    try:
        _make_test_module(tmp)
        result = pack_module("test_mod", source_dir=str(Path(tmp) / "test_mod"), output_dir=str(out))
        sha_path = Path(result["zip_path"] + ".sha256")
        assert sha_path.exists()
        stored_hash = sha_path.read_text().strip()
        actual_hash = hashlib.sha256(Path(result["zip_path"]).read_bytes()).hexdigest()
        assert stored_hash == actual_hash
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("  ✓ .sha256 checksum correct")


def test_pack_all():
    """③ 打包全部模块"""
    from tools.pack_module import pack_all
    tmp = tempfile.mkdtemp()
    out = Path(tmp) / "outputs"
    try:
        _make_test_module(tmp, "mod_a")
        _make_test_module(tmp, "mod_b")
        results = pack_all(source_dir=tmp, output_dir=str(out))
        assert len(results) == 2
        assert all(r["file_count"] >= 2 for r in results)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("  ✓ pack all modules")


def test_missing_manifest():
    """④ 缺 manifest 时打包失败"""
    from tools.pack_module import pack_module
    tmp = tempfile.mkdtemp()
    try:
        mdir = Path(tmp) / "no_manifest"
        mdir.mkdir()
        (mdir / "__init__.py").write_text("")
        try:
            pack_module("no_manifest", source_dir=tmp, output_dir=str(Path(tmp) / "out"))
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("  ✓ missing manifest → FileNotFoundError")


def test_output_dir_auto_created():
    """⑤ 输出目录自动创建"""
    from tools.pack_module import pack_module
    tmp = tempfile.mkdtemp()
    out = Path(tmp) / "new" / "nested" / "outputs"
    try:
        _make_test_module(tmp)
        result = pack_module("test_mod", source_dir=str(Path(tmp) / "test_mod"), output_dir=str(out))
        zip_path = Path(result["zip_path"])
        assert zip_path.parent.exists()
        assert zip_path.exists()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("  ✓ output dir auto-created")


def test_incremental_pack_hash_differs():
    """⑥ 增量打包→不同内容产生不同 hash"""
    from tools.pack_module import pack_module
    tmp = tempfile.mkdtemp()
    out = Path(tmp) / "outputs"
    try:
        mdir = _make_test_module(tmp, "ver_mod", version="1.0.0")
        r1 = pack_module("ver_mod", source_dir=tmp, output_dir=str(out))

        # 修改版本号
        mf = mdir / "manifest.json"
        manifest = json.loads(mf.read_text())
        manifest["version"] = "1.1.0"
        mf.write_text(json.dumps(manifest, indent=2))
        r2 = pack_module("ver_mod", source_dir=tmp, output_dir=str(out))

        assert r1["sha256"] != r2["sha256"], "hash should differ after version change"
        assert r1["version"] == "1.0.0"
        assert r2["version"] == "1.1.0"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("  ✓ incremental pack: hash differs")


if __name__ == "__main__":
    tests = [
        test_pack_single_module,
        test_pack_outputs_sha256,
        test_pack_all,
        test_missing_manifest,
        test_output_dir_auto_created,
        test_incremental_pack_hash_differs,
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
