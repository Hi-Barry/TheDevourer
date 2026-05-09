"""TheDevourer — chroma_client 插件模块"""
from core.chroma_client import ChromaClient, init_chroma


def plugin_load():
    pass


def plugin_unload():
    pass


__all__ = ["ChromaClient", "init_chroma", "plugin_load", "plugin_unload"]
