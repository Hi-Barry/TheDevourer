"""TheDevourer — storage_manager 插件模块"""
from core.storage_manager import StorageManager


def plugin_load():
    pass


def plugin_unload():
    pass


__all__ = ["StorageManager", "plugin_load", "plugin_unload"]
