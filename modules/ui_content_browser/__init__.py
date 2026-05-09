"""TheDevourer — ui_content_browser 插件模块"""


def plugin_load():
    pass


def plugin_unload():
    pass


def create_content_browser(db, storage_manager=None):
    """创建内容浏览器（延迟导入 PySide6）"""
    from ui.content_browser import ContentBrowser
    return ContentBrowser(db, storage_manager)


__all__ = [
    "plugin_load", "plugin_unload",
    "create_content_browser",
]
