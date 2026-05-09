"""大嘴怪 — 日志模块 初始化+输出+文件+幂等 测试"""
import sys, os, tempfile, shutil, logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')

# 重置全局 logger 状态（每次测试前隔离）
import core.logger as log_mod


def test_init_logger_returns_instance():
    """① init_logger 返回 Logger 实例"""
    # 重置
    log_mod._logger = None
    log_dir = tempfile.mkdtemp()
    try:
        logger = log_mod.init_logger(log_dir, logging.DEBUG)
        assert isinstance(logger, logging.Logger)
        assert logger.name == "big_mouth"
        assert logger.level == logging.DEBUG
        print("  ✓ init_logger returns Logger instance")
    finally:
        log_mod._logger = None
        shutil.rmtree(log_dir, ignore_errors=True)


def test_log_levels_no_error():
    """② INFO/WARNING/ERROR 各级别输出不抛异常"""
    log_mod._logger = None
    log_dir = tempfile.mkdtemp()
    try:
        logger = log_mod.init_logger(log_dir, logging.DEBUG)
        logger.info("test info message")
        logger.warning("test warning message")
        logger.error("test error message")
        # 不应该抛异常就是成功
        print("  ✓ log levels INFO/WARNING/ERROR OK")
    finally:
        log_mod._logger = None
        shutil.rmtree(log_dir, ignore_errors=True)


def test_file_writer_creates_logfile():
    """③ RotatingFileHandler 写入日志文件"""
    log_mod._logger = None
    log_dir = tempfile.mkdtemp()
    try:
        logger = log_mod.init_logger(log_dir, logging.DEBUG)
        test_msg = "TEST_UNIQUE_LOG_LINE_xyz"
        logger.info(test_msg)

        # 检查日志文件中有内容
        log_file = Path(log_dir) / "big_mouth.log"
        assert log_file.exists(), f"日志文件不存在: {log_file}"
        content = log_file.read_text()
        assert test_msg in content, f"内容不包含测试消息: {content[:200]}"
        print("  ✓ RotatingFileHandler writes to file")
    finally:
        log_mod._logger = None
        shutil.rmtree(log_dir, ignore_errors=True)


def test_init_logger_idempotent():
    """④ 重复 init_logger 返回同一实例"""
    log_mod._logger = None
    log_dir = tempfile.mkdtemp()
    try:
        logger1 = log_mod.init_logger(log_dir, logging.DEBUG)
        logger2 = log_mod.init_logger(log_dir, logging.INFO)  # 不同 level
        assert logger1 is logger2
        # 第一次的 level 保留（不覆盖）
        assert logger1.level == logging.DEBUG
        print("  ✓ init_logger idempotent")
    finally:
        log_mod._logger = None
        shutil.rmtree(log_dir, ignore_errors=True)


def test_get_logger_auto_init():
    """⑤ get_logger 未初始化时自动创建"""
    log_mod._logger = None
    try:
        logger = log_mod.get_logger()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "big_mouth"
        print("  ✓ get_logger auto-initializes")
    finally:
        log_mod._logger = None


# ── 运行入口 ──────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_init_logger_returns_instance,
        test_log_levels_no_error,
        test_file_writer_creates_logfile,
        test_init_logger_idempotent,
        test_get_logger_auto_init,
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
