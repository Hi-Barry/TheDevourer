"""test_plugin_ui_settings_dialog"""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')
from core.module_loader import ModuleLoader
def _p(): return str(Path(__file__).resolve().parent.parent / "modules" / "ui_settings_dialog")
def test_load():
    L=ModuleLoader(); m=L.load(_p()); assert m.name=="ui_settings_dialog"; L.cleanup(); print("✓ load")
def test_entry_points():
    L=ModuleLoader(); m=L.load(_p())
    for ep in ["functions.plugin_load","functions.plugin_unload","functions.create_settings_dialog"]:
        assert ep in m.entry_points
    L.cleanup(); print("✓ entry_points")
def test_hooks():
    L=ModuleLoader(); m=L.load(_p())
    assert callable(m.instance.plugin_load) and callable(m.instance.plugin_unload); L.cleanup(); print("✓ hooks")
def test_create_factory():
    L=ModuleLoader(); m=L.load(_p()); cf=m.entry_points["functions.create_settings_dialog"]
    assert callable(cf); L.cleanup(); print("✓ create_factory callable")
if __name__=="__main__":
    for t in [test_load,test_entry_points,test_hooks,test_create_factory]:
        try: t()
        except Exception as e: import traceback; print(f"✗ {t.__name__}: {e}"); traceback.print_exc()
