"""TheDevourer — file_watcher 插件模块"""
from core.signal_bus import EventBus
from core.file_watcher import FileWatcher, RepoWatcherHandler


def plugin_load():
    EventBus().subscribe("storage/stored", _on_item_stored, module="file_watcher")


def plugin_unload():
    EventBus().clear_module("file_watcher")


def _on_item_stored(data: dict):
    pass


__all__ = ["FileWatcher", "RepoWatcherHandler", "plugin_load", "plugin_unload"]
