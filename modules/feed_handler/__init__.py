"""TheDevourer — feed_handler 插件模块

投喂处理：FeedItem 数据模型 + URL/文本解析 + 投喂队列。
"""
from core.feed_handler import (
    FeedItem, FeedSourceType, FeedQueueWorker,
    extract_urls, is_url, fetch_url_title, compute_md5, parse_mime_data,
)
from core.signal_bus import EventBus


def plugin_load():
    """模块加载时注册信号"""
    EventBus().subscribe("feed/received", _on_feed_received, module="feed_handler")


def plugin_unload():
    """模块卸载时清理信号"""
    EventBus().clear_module("feed_handler")


def _on_feed_received(data: dict) -> None:
    """投喂接收后的内部处理"""
    pass


__all__ = [
    "FeedItem", "FeedSourceType", "FeedQueueWorker",
    "extract_urls", "is_url", "fetch_url_title", "compute_md5", "parse_mime_data",
    "plugin_load", "plugin_unload",
]
