"""test_plugin_kb_qa"""
import sys, os, tempfile, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')
from core.module_loader import ModuleLoader
from core.db import Database

def _p(): return str(Path(__file__).resolve().parent.parent / "modules" / "kb_qa")

def test_load():
    L = ModuleLoader(); m = L.load(_p()); assert m.name == "kb_qa"; L.cleanup(); print("✓ load")
def test_entry_points():
    L = ModuleLoader(); m = L.load(_p())
    assert "classes.KbQA" in m.entry_points; assert "functions.create_kb_qa" in m.entry_points; L.cleanup(); print("✓ entry_points")
def test_factory():
    L = ModuleLoader(); m = L.load(_p()); ck = m.entry_points["functions.create_kb_qa"]
    tmp=tempfile.mkdtemp(); db=Database(os.path.join(tmp,"t.db")); db.init_schema()
    kqa = ck(db,None); assert kqa is not None; shutil.rmtree(tmp,ignore_errors=True); L.cleanup(); print("✓ factory")
def test_new_session():
    L = ModuleLoader(); m = L.load(_p()); ck = m.entry_points["functions.create_kb_qa"]
    tmp=tempfile.mkdtemp(); db=Database(os.path.join(tmp,"t.db")); db.init_schema()
    kqa = ck(db,None); s1=kqa.new_session(); s2=kqa.new_session(); assert s1!=s2
    shutil.rmtree(tmp,ignore_errors=True); L.cleanup(); print("✓ new_session")
def test_empty_kb_ask():
    L = ModuleLoader(); m = L.load(_p()); ck = m.entry_points["functions.create_kb_qa"]
    tmp=tempfile.mkdtemp(); db=Database(os.path.join(tmp,"t.db")); db.init_schema()
    kqa = ck(db,None); ans = kqa.ask("any question"); assert len(ans)>0
    shutil.rmtree(tmp,ignore_errors=True); L.cleanup(); print("✓ empty KB ask")
def test_conversation():
    L = ModuleLoader(); m = L.load(_p()); ck = m.entry_points["functions.create_kb_qa"]
    tmp=tempfile.mkdtemp(); db=Database(os.path.join(tmp,"t.db")); db.init_schema()
    kqa = ck(db,None); sid = kqa.new_session()
    kqa.save_conversation(sid,"user","hello"); kqa.save_conversation(sid,"assistant","hi")
    h = kqa.get_conversation(sid); assert len(h)==2; assert h[0]["role"]=="user"
    shutil.rmtree(tmp,ignore_errors=True); L.cleanup(); print("✓ conversation")
def test_hooks():
    L = ModuleLoader(); m = L.load(_p()); assert callable(m.instance.plugin_load); assert callable(m.instance.plugin_unload); L.cleanup(); print("✓ hooks")
if __name__=="__main__":
    for t in [test_load,test_entry_points,test_factory,test_new_session,test_empty_kb_ask,test_conversation,test_hooks]:
        try: t()
        except Exception as e: import traceback; print(f"✗ {t.__name__}: {e}"); traceback.print_exc()
