"""大嘴怪 — 日志模块"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

_logger: logging.Logger | None = None
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DATE_FORMAT = "%H:%M:%S"


def init_logger(log_dir: str = None, level: int = logging.INFO) -> logging.Logger:
    """初始化日志系统，返回模块级 logger"""
    global _logger

    if _logger is not None:
        return _logger

    _logger = logging.getLogger("big_mouth")
    _logger.setLevel(level)

    # 控制台 handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(_LOG_FORMAT, _LOG_DATE_FORMAT))
    _logger.addHandler(console)

    # 文件 handler（如果提供了目录）
    if log_dir:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            Path(log_dir) / "big_mouth.log",
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        _logger.addHandler(file_handler)

    return _logger


def get_logger() -> logging.Logger:
    if _logger is None:
        return init_logger()
    return _logger
