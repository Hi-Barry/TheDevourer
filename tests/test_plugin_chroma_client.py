"""test_plugin_chroma_client"""
import sys, os, tempfile, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')
from core.module_loader import ModuleLoader

def _p(): return str(Path(__file__).resolve().parent.parent / "modules" / "chroma_client")

def test_load():
    L = ModuleLoader(); m = L.load(_p()); assert m.name == "chroma_client"; L.cleanup(); print("✓ load")
def test_entry_points():
    L = ModuleLoader(); m = L.load(_p())
    assert "classes.ChromaClient" in m.entry_points; assert "functions.init_chroma" in m.entry_points; L.cleanup(); print("✓ entry_points")
def test_factory():
    L = ModuleLoader(); m = L.load(_p()); ic = m.entry_points["functions.init_chroma"]
    try:
        tmp = tempfile.mkdtemp(); client = ic(tmp)
        assert client is not None; client.get_or_create(); assert client.count()==0
        shutil.rmtree(tmp,ignore_errors=True)
    except ImportError as e:
        print(f"  ⚠ skip: {e}")
    L.cleanup(); print("✓ init_chroma factory")
def test_hooks():
    L = ModuleLoader(); m = L.load(_p()); assert callable(m.instance.plugin_load); assert callable(m.instance.plugin_unload); L.cleanup(); print("✓ hooks")
if __name__=="__main__":
    for t in [test_load,test_entry_points,test_factory,test_hooks]:
        try: t()
        except Exception as e: import traceback; print(f"✗ {t.__name__}: {e}"); traceback.print_exc()
