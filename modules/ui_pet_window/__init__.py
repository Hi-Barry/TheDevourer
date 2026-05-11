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
    """创建精灵窗口（延迟导入 PySide6）。feed_queue 可选，默认使用新队列。"""
    if feed_queue is None:
        from core.feed_handler import FeedQueueWorker
        feed_queue = FeedQueueWorker()

    # 连接投喂信号到 UI
    feed_queue.item_started.connect(lambda item: EventBus().publish("feed/started", item=item))
    feed_queue.item_finished.connect(lambda item, ok, msg: EventBus().publish("feed/done", item=item, ok=ok, msg=msg))

    from ui.pet_window import PetWindow
    return PetWindow(feed_queue=feed_queue)


__all__ = [
    "plugin_load", "plugin_unload",
    "create_pet_window",
]
