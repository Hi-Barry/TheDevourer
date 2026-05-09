"""TheDevourer — ui_question_dialog 插件模块"""
from core.signal_bus import EventBus


def plugin_load():
    EventBus().subscribe("qa/token", _on_qa_token, module="ui_question_dialog")


def plugin_unload():
    EventBus().clear_module("ui_question_dialog")


def _on_qa_token(data: dict):
    pass


def create_question_dialog():
    """创建提问对话框（延迟导入 PySide6）"""
    from ui.question_dialog import QuestionDialog
    return QuestionDialog()


__all__ = [
    "plugin_load", "plugin_unload",
    "create_question_dialog",
]
