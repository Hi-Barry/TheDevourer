"""test_plugin_file_watcher"""
import sys, os, tempfile, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')
from core.module_loader import ModuleLoader
from core.file_watcher import RepoWatcherHandler

def _p(): return str(Path(__file__).resolve().parent.parent / "modules" / "file_watcher")

def test_load():
    L = ModuleLoader(); m = L.load(_p()); assert m.name == "file_watcher"; L.cleanup(); print("✓ load")
def test_entry_points():
    L = ModuleLoader(); m = L.load(_p())
    assert "classes.FileWatcher" in m.entry_points; assert "classes.RepoWatcherHandler" in m.entry_points; L.cleanup(); print("✓ entry_points")
def test_should_skip():
    L = ModuleLoader(); m = L.load(_p()); RWH = m.entry_points["classes.RepoWatcherHandler"]
    h=RWH(); assert h._should_skip("/tmp/.hidden") is True; assert h._should_skip("/tmp/test.py") is False; L.cleanup(); print("✓ should_skip")
def test_debounce():
    L = ModuleLoader(); m = L.load(_p()); RWH = m.entry_points["classes.RepoWatcherHandler"]
    h=RWH(); assert h._debounce_check("/tmp/a") is True; assert h._debounce_check("/tmp/a") is False; L.cleanup(); print("✓ debounce")
def test_hooks():
    L = ModuleLoader(); m = L.load(_p()); assert callable(m.instance.plugin_load); assert callable(m.instance.plugin_unload); L.cleanup(); print("✓ hooks")
if __name__=="__main__":
    for t in [test_load,test_entry_points,test_should_skip,test_debounce,test_hooks]:
        try: t()
        except Exception as e: import traceback; print(f"✗ {t.__name__}: {e}"); traceback.print_exc()
