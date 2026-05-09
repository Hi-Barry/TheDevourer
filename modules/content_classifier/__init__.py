"""TheDevourer — content_classifier 插件模块"""
from core.content_classifier import ContentClassifier


def plugin_load():
    pass


def plugin_unload():
    pass


__all__ = ["ContentClassifier", "plugin_load", "plugin_unload"]
