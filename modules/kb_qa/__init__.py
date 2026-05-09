"""TheDevourer — kb_qa 插件模块"""
from core.kb_qa import KbQA, create_kb_qa


def plugin_load():
    pass


def plugin_unload():
    pass


__all__ = ["KbQA", "create_kb_qa", "plugin_load", "plugin_unload"]
