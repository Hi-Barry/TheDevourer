"""test_plugin_file_classifier"""
import sys, tempfile, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')
from core.module_loader import ModuleLoader

def _p(): return str(Path(__file__).resolve().parent.parent / "modules" / "file_classifier")

def test_load():
    L = ModuleLoader(); m = L.load(_p()); assert m.name == "file_classifier"; L.cleanup(); print("✓ load")
def test_entry_points():
    L = ModuleLoader(); m = L.load(_p())
    for ep in ["classes.FileClassifier","classes.FileInfo"]: assert ep in m.entry_points
    L.cleanup(); print("✓ entry_points")
def test_classify():
    L = ModuleLoader(); m = L.load(_p()); FC = m.entry_points["classes.FileClassifier"]
    f = FC(); tmp = tempfile.mkdtemp()
    p = Path(tmp)/"test.py"; p.write_text("x=1"); info = f.identify(str(p))
    assert info.content_type == "document"; assert info.error == ""
    shutil.rmtree(tmp,ignore_errors=True); L.cleanup(); print("✓ classify .py")
def test_nonexistent():
    L = ModuleLoader(); m = L.load(_p()); FC = m.entry_points["classes.FileClassifier"]
    info = FC().identify("/nonexistent"); assert info.error != ""
    L.cleanup(); print("✓ nonexistent")
def test_hooks():
    L = ModuleLoader(); m = L.load(_p()); assert callable(m.instance.plugin_load)
    assert callable(m.instance.plugin_unload); L.cleanup(); print("✓ hooks")
def test_text_file():
    L = ModuleLoader(); m = L.load(_p()); FC = m.entry_points["classes.FileClassifier"]
    tmp = tempfile.mkdtemp(); p = Path(tmp)/"note.md"; p.write_text("# hello")
    info = FC().identify(str(p)); assert info.text_length>0
    shutil.rmtree(tmp,ignore_errors=True); L.cleanup(); print("✓ .md text extraction")
if __name__=="__main__":
    for t in [test_load,test_entry_points,test_classify,test_nonexistent,test_hooks,test_text_file]:
        try: t()
        except Exception as e: import traceback; print(f"✗ {t.__name__}: {e}"); traceback.print_exc()
