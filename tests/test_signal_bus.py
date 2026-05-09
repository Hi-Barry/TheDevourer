"""TheDevourer — SignalBus 信号总线 测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')

from core.signal_bus import EventBus


def setup():
    """重置总线，确保测试隔离"""
    bus = EventBus()
    bus.reset()
    return bus


def test_subscribe_publish():
    """① subscribe→publish 触发回调"""
    bus = setup()
    received = []

    def callback(data):
        received.append(data)

    bus.subscribe("feed/received", callback)
    bus.publish("feed/received", item_id="123", title="测试")

    assert len(received) == 1
    assert received[0]["item_id"] == "123"
    assert received[0]["title"] == "测试"
    print("  ✓ subscribe→publish triggers callback")


def test_multiple_subscribers():
    """② 多个订阅者全部收到"""
    bus = setup()
    results = []

    def cb1(data): results.append("cb1")
    def cb2(data): results.append("cb2")
    def cb3(data): results.append("cb3")

    bus.subscribe("feed/received", cb1)
    bus.subscribe("feed/received", cb2)
    bus.subscribe("feed/received", cb3)
    bus.publish("feed/received")

    assert len(results) == 3
    assert results == ["cb1", "cb2", "cb3"]
    print("  ✓ multiple subscribers all triggered")


def test_unsubscribe():
    """③ 取消订阅后不再触发"""
    bus = setup()
    results = []

    def cb(data): results.append("got it")

    bus.subscribe("feed/received", cb)
    bus.publish("feed/received")
    assert len(results) == 1

    bus.unsubscribe("feed/received", cb)
    bus.publish("feed/received")
    assert len(results) == 1  # 不变
    print("  ✓ unsubscribe stops triggering")


def test_event_parameters():
    """④ 事件参数传递完整"""
    bus = setup()
    captured = {}

    def callback(data):
        captured.update(data)
        assert "item" in data
        assert "url" in data

    bus.subscribe("feed/done", callback)
    bus.publish("feed/done", item={"name": "test"}, url="https://example.com", ok=True)

    assert captured.get("ok") is True
    assert captured.get("url") == "https://example.com"
    print("  ✓ event parameters passed correctly")


def test_one_failure_does_not_block_others():
    """⑤ 单个订阅者失败不影响其他"""
    bus = setup()
    results = []

    def failing(data): raise ValueError("oops")

    def ok(data):
        results.append("ok")

    bus.subscribe("feed/received", failing)
    bus.subscribe("feed/received", ok)
    bus.publish("feed/received", test=True)

    assert len(results) == 1
    assert results[0] == "ok"
    print("  ✓ one failure does not block others")


def test_different_events_isolated():
    """⑥ 不同事件不相互干扰"""
    bus = setup()
    results = set()

    def cb_feed(data): results.add("feed")

    def cb_qa(data): results.add("qa")

    def cb_watcher(data): results.add("watcher")

    bus.subscribe("feed/received", cb_feed)
    bus.subscribe("qa/asked", cb_qa)
    bus.subscribe("watcher/file_created", cb_watcher)

    bus.publish("feed/received")
    assert results == {"feed"}
    assert "qa" not in results
    assert "watcher" not in results

    bus.publish("qa/asked")
    assert results == {"feed", "qa"}

    bus.publish("watcher/file_created")
    assert results == {"feed", "qa", "watcher"}

    print("  ✓ different events isolated")


def test_clear_module():
    """⑦ clear_module 清理模块所有订阅"""
    bus = setup()
    results = []

    def cb1(data): results.append("cb1")

    def cb2(data): results.append("cb2")

    bus.subscribe("feed/received", cb1, module="mod_a")
    bus.subscribe("feed/received", cb2, module="mod_b")
    bus.publish("feed/received")
    assert len(results) == 2

    bus.clear_module("mod_a")
    bus.publish("feed/received")
    assert len(results) == 3  # cb1 不再触发，只有 cb2
    assert results == ["cb1", "cb2", "cb2"]
    print("  ✓ clear_module removes module subscriptions")


def test_subscriber_count():
    """⑧ subscriber_count 统计正确"""
    bus = setup()
    assert bus.subscriber_count == 0

    def cb(data): pass

    bus.subscribe("feed/received", cb)
    bus.subscribe("qa/asked", cb)
    assert bus.subscriber_count == 2

    bus.unsubscribe("feed/received", cb)
    assert bus.subscriber_count == 1
    print("  ✓ subscriber_count correct")


# ── 运行入口 ──────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_subscribe_publish,
        test_multiple_subscribers,
        test_unsubscribe,
        test_event_parameters,
        test_one_failure_does_not_block_others,
        test_different_events_isolated,
        test_clear_module,
        test_subscriber_count,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            import traceback
            print(f"  ✗ {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{'='*40}\n结果: {passed}/{len(tests)} 通过")
