"""大嘴怪 — Config 全属性/方法/边界 测试"""
import sys, os, json, tempfile, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')

from core.config import Config, _DEFAULTS


def test_config_get_set():
    """get/set 基本读写"""
    cfg = Config()
    cfg._use_qt = False
    cfg._store = dict(_DEFAULTS)

    cfg.set("repo_path", "/tmp/test_repo")
    assert cfg.get("repo_path") == "/tmp/test_repo"
    assert cfg.repo_path == "/tmp/test_repo"
    print("  ✓ get/set basic")


def test_config_default_fallback():
    """不存在的 key 返回 _DEFAULTS 中的值或自定义默认值"""
    cfg = Config()
    cfg._use_qt = False
    cfg._store = {}

    # key 在 _DEFAULTS 中存在 → 返回 _DEFAULTS 的值
    repo_default = cfg.get("repo_path")
    assert repo_default is not None
    assert repo_default == str(Path.home() / "大嘴怪仓库")

    # key 不存在于任何地方 → 返回自定义默认值
    fallback = cfg.get("nonexistent_key", "fallback")
    assert fallback == "fallback"

    print("  ✓ default fallback")


def test_bool_type_conversion():
    """布尔属性从字符串正确转换"""
    cfg = Config()
    cfg._use_qt = False
    cfg._store = dict(_DEFAULTS)

    # True 变体
    for true_val in [True, "true", "1", "yes", 1]:
        cfg._store["autostart"] = true_val
        assert cfg.autostart is True, f"autostart({true_val}) should be True"

    # False 变体
    for false_val in [False, "false", "0", "no", "", 0, None]:
        cfg._store["autostart"] = false_val
        assert cfg.autostart is False, f"autostart({false_val}) should be False"
    print("  ✓ bool type conversion")


def test_first_run_default():
    """首次运行 first_run=True"""
    cfg = Config()
    cfg._use_qt = False
    cfg._store = {}
    assert cfg.first_run is True
    print("  ✓ first_run default True")


def test_all_property_getters():
    """所有 property getter 不抛异常 + 返回正确类型"""
    cfg = Config()
    cfg._use_qt = False
    cfg._store = dict(_DEFAULTS)

    getters = [
        ("repo_path", str),
        ("window_x", int),
        ("window_y", int),
        ("window_scale", float),
        ("always_on_top", bool),
        ("autostart", bool),
        ("clipboard_monitor", bool),
        ("auto_index", bool),
        ("watchdog_enabled", bool),
        ("llm_backend", str),
        ("ollama_endpoint", str),
        ("ollama_model", str),
        ("api_endpoint", str),
        ("api_key", str),
        ("api_model", str),
        ("embedding_model", str),
        ("embedding_device", str),
        ("max_context_chunks", int),
        ("max_history_rounds", int),
    ]

    for name, expected_type in getters:
        val = getattr(cfg, name)
        assert isinstance(val, expected_type), f"{name} type: expected {expected_type}, got {type(val)} ({val})"

    print(f"  ✓ {len(getters)} property getters all OK")


def test_setters():
    """setter 写后读取验证"""
    cfg = Config()
    cfg._use_qt = False
    cfg._store = dict(_DEFAULTS)

    # repo_path setter
    cfg.repo_path = "/tmp/set_test"
    assert cfg.repo_path == "/tmp/set_test"
    assert cfg.get("repo_path") == "/tmp/set_test"

    # autostart setter
    cfg.autostart = True
    assert cfg.autostart is True
    cfg.autostart = False
    assert cfg.autostart is False

    # llm_backend setter
    cfg.llm_backend = "openai_compatible"
    assert cfg.llm_backend == "openai_compatible"

    # api_key setter
    cfg.api_key = "sk-test-123"
    assert cfg.api_key == "sk-test-123"

    # first_run setter
    cfg.first_run = False
    assert cfg.first_run is False

    print("  ✓ all setters OK")


def test_ensure_paths():
    """ensure_paths 创建所有必需目录"""
    tmp = tempfile.mkdtemp()
    try:
        cfg = Config()
        cfg._use_qt = False
        cfg._store = dict(_DEFAULTS)
        cfg._store["repo_path"] = tmp

        cfg.ensure_paths()
        assert os.path.isdir(tmp)
        assert os.path.isdir(os.path.join(tmp, "files"))
        assert os.path.isdir(os.path.join(tmp, "chroma_db"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("  ✓ ensure_paths creates directories")


def test_db_path_property():
    """db_path/chroma_path/files_path 拼接正确"""
    cfg = Config()
    cfg._use_qt = False
    cfg._store = dict(_DEFAULTS)
    cfg._store["repo_path"] = "/test/repo"

    assert cfg.db_path == "/test/repo/big_mouth.db"
    assert cfg.chroma_path == "/test/repo/chroma_db"
    assert cfg.files_path == "/test/repo/files"
    print("  ✓ db_path/chroma_path/files_path OK")


def test_all_settings():
    """all_settings 返回完整字典"""
    cfg = Config()
    cfg._use_qt = False
    cfg._store = dict(_DEFAULTS)

    settings = cfg.all_settings()
    for key in _DEFAULTS:
        assert key in settings, f"Missing key: {key}"
    assert len(settings) == len(_DEFAULTS)
    print(f"  ✓ all_settings: {len(settings)} keys")


def test_window_coord_persistence():
    """窗口坐标写入后恢复"""
    cfg = Config()
    cfg._use_qt = False
    cfg._store = dict(_DEFAULTS)

    cfg.window_x = 500
    cfg.window_y = 300
    assert cfg.window_x == 500
    assert cfg.window_y == 300
    print("  ✓ window coordinate persistence")


# ── 运行入口 ──────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_config_get_set,
        test_config_default_fallback,
        test_bool_type_conversion,
        test_first_run_default,
        test_all_property_getters,
        test_setters,
        test_ensure_paths,
        test_db_path_property,
        test_all_settings,
        test_window_coord_persistence,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
    print(f"\n{'='*40}\n结果: {passed}/{len(tests)} 通过")
