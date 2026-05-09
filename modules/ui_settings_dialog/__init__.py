"""TheDevourer — ui_settings_dialog 插件模块"""


def plugin_load():
    pass


def plugin_unload():
    pass


def create_settings_dialog():
    """创建设置对话框（延迟导入 PySide6）"""
    from ui.settings_dialog import SettingsDialog
    return SettingsDialog()


__all__ = [
    "plugin_load", "plugin_unload",
    "create_settings_dialog",
]
