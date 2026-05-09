"""TheDevourer — file_classifier 插件模块"""
from core.file_classifier import FileClassifier, FileInfo


def plugin_load():
    pass


def plugin_unload():
    pass


__all__ = ["FileClassifier", "FileInfo", "plugin_load", "plugin_unload"]
