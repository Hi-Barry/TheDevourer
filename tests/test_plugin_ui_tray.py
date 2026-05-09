"""test_plugin_ui_tray"""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')
from core.module_loader import ModuleLoader
from core.signal_bus import EventBus
def _p(): return str(Path(__file__).resolve().parent.parent / "modules" / "ui_tray")
def test_load():
    L=ModuleLoader(); m=L.load(_p()); assert m.name=="ui_tray"; L.cleanup(); print("✓ load")
def test_entry_points():
    L=ModuleLoader(); m=L.load(_p())
    for ep in ["functions.plugin_load","functions.plugin_unload","functions.create_tray_icon"]:
        assert ep in m.entry_points
    L.cleanup(); print("✓ entry_points")
def test_hooks():
    L=ModuleLoader(); m=L.load(_p())
    assert callable(m.instance.plugin_load) and callable(m.instance.plugin_unload); L.cleanup(); print("✓ hooks")
def test_signal_subscription():
    bus=EventBus(); bus.reset()
    L=ModuleLoader(); L.load(_p())
    assert bus.subscriber_count>=1
    bus.clear_module("ui_tray"); L.cleanup(); print("✓ signal subscriptions")
if __name__=="__main__":
    for t in [test_load,test_entry_points,test_hooks,test_signal_subscription]:
        try: t()
        except Exception as e: import traceback; print(f"✗ {t.__name__}: {e}"); traceback.print_exc()
