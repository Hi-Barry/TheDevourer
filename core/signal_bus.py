"""TheDevourer — SignalBus 信号总线

模块间通信的核心纽带。所有功能/UI 模块不直接 import 彼此，
通过 publish/subscribe 模式解耦通信。
"""
import inspect
import threading
from collections import defaultdict
from typing import Callable, Any

from core.logger import get_logger

logger = get_logger()


class EventBus:
    """全局事件总线，单例模式"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._subscribers: dict[str, list[dict]] = {}
                    cls._instance._module_subscribers: dict[str, list[str]] = defaultdict(list)
        return cls._instance

    def subscribe(self, event: str, callback: Callable, module: str = "") -> None:
        """
        订阅事件。
        event: 事件名，如 'feed/received'
        callback: 回调函数，接收 data dict
        module: 订阅者模块名（用于卸载时清理）
        """
        if event not in self._subscribers:
            self._subscribers[event] = []

        entry = {"callback": callback, "module": module}
        self._subscribers[event].append(entry)

        if module:
            self._module_subscribers[module].append(event)

        logger.debug(f"SignalBus: {module or 'unknown'} subscribed {event}")

    def unsubscribe(self, event: str, callback: Callable) -> None:
        """取消订阅"""
        if event not in self._subscribers:
            return
        self._subscribers[event] = [
            e for e in self._subscribers[event] if e["callback"] is not callback
        ]
        logger.debug(f"SignalBus: unsubscribed {event}")

    def publish(self, event: str, **data) -> None:
        """
        发布事件。
        所有订阅该事件的回调依次被调用，异常不传播（单回调失败不影响其他）。
        """
        if event not in self._subscribers:
            return

        for entry in self._subscribers[event]:
            try:
                entry["callback"](data)
            except Exception as e:
                logger.warning(
                    f"SignalBus: {entry['module'] or 'unknown'} callback error "
                    f"for {event}: {e}"
                )

    def clear_module(self, module: str) -> None:
        """清除某模块的所有订阅（模块卸载时调用）"""
        if module not in self._module_subscribers:
            return

        for event in list(self._module_subscribers[module]):
            if event in self._subscribers:
                self._subscribers[event] = [
                    e for e in self._subscribers[event] if e["module"] != module
                ]

        del self._module_subscribers[module]
        logger.debug(f"SignalBus: cleared all subscriptions for {module}")

    @property
    def subscriber_count(self) -> int:
        """所有事件的订阅者总数"""
        return sum(len(subs) for subs in self._subscribers.values())

    def reset(self) -> None:
        """重置总线（测试用）"""
        self._subscribers.clear()
        self._module_subscribers.clear()
