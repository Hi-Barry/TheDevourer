"""TheDevourer — ui_tray 插件模块"""
from core.signal_bus import EventBus


def plugin_load():
    EventBus().subscribe("ui/pet_double_clicked", _show_pet, module="ui_tray")


def plugin_unload():
    EventBus().clear_module("ui_tray")


def _show_pet(data: dict):
    pass


def create_tray_icon():
    """创建系统托盘（需 PySide6）"""
    from PySide6.QtWidgets import QSystemTrayIcon
    return QSystemTrayIcon()


__all__ = [
    "plugin_load", "plugin_unload",
    "create_tray_icon",
]
