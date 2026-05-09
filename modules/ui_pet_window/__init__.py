"""TheDevourer — ui_pet_window 插件模块"""
from core.signal_bus import EventBus
# PySide6 在 plugin_load/plugin_unload 中延迟导入


def plugin_load():
    EventBus().subscribe("feed/received", _on_feed_received, module="ui_pet_window")
    EventBus().subscribe("feed/done", _on_feed_done, module="ui_pet_window")


def plugin_unload():
    EventBus().clear_module("ui_pet_window")


def _on_feed_received(data: dict):
    pass


def _on_feed_done(data: dict):
    pass


def create_pet_window(feed_queue=None):
    """创建精灵窗口（延迟导入 PySide6）"""
    from ui.pet_window import PetWindow
    return PetWindow(feed_queue=feed_queue)


__all__ = [
    "plugin_load", "plugin_unload",
    "create_pet_window",
]
