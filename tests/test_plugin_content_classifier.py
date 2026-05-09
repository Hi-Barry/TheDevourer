"""test_plugin_content_classifier"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')
from core.module_loader import ModuleLoader
from core.file_classifier import FileInfo

def _p(): return str(Path(__file__).resolve().parent.parent / "modules" / "content_classifier")

def test_load():
    L = ModuleLoader(); m = L.load(_p()); assert m.name == "content_classifier"; L.cleanup(); print("✓ load")
def test_entry_points():
    L = ModuleLoader(); m = L.load(_p()); assert "classes.ContentClassifier" in m.entry_points; L.cleanup(); print("✓ entry_points")
def test_ext_classify():
    L = ModuleLoader(); m = L.load(_p()); CC = m.entry_points["classes.ContentClassifier"]
    info = FileInfo(file_path="main.py",file_name="main.py",text_preview="python code",mime_type="text/x-python")
    cat,tags = CC().classify(info); assert "代码" in cat; assert "Python" in tags; L.cleanup(); print("✓ extension classify")
def test_url():
    L = ModuleLoader(); m = L.load(_p()); CC = m.entry_points["classes.ContentClassifier"]
    cat,_ = CC().classify_url("https://github.com/repo"); assert "技术" in cat; L.cleanup(); print("✓ URL classify")
def test_keyword():
    L = ModuleLoader(); m = L.load(_p()); CC = m.entry_points["classes.ContentClassifier"]
    info = FileInfo(file_path="a.txt",file_name="a.txt",text_preview="Python Docker LLM",mime_type="text/plain")
    _,tags = CC().classify(info); assert "Python" in tags; assert "DevOps" in tags; L.cleanup(); print("✓ keyword tags")
def test_empty():
    L = ModuleLoader(); m = L.load(_p()); CC = m.entry_points["classes.ContentClassifier"]
    info = FileInfo(); cat,tags = CC().classify(info); assert cat=="其他" or cat is not None; L.cleanup(); print("✓ empty input")
if __name__=="__main__":
    for t in [test_load,test_entry_points,test_ext_classify,test_url,test_keyword,test_empty]:
        try: t()
        except Exception as e: import traceback; print(f"✗ {t.__name__}: {e}"); traceback.print_exc()
