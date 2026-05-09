"""test_plugin_storage_manager"""
import sys, os, tempfile, shutil, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')
from core.module_loader import ModuleLoader
from core.db import Database

def _p(x=""): b=Path(__file__).resolve().parent.parent; return str(b/"modules"/"storage_manager") if not x else x

def setup():
    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp,"test.db")); db.init_schema()
    cfg = type("cfg",(),{"repo_path":tmp,"files_path":os.path.join(tmp,"files"),"chroma_path":os.path.join(tmp,"chroma_db"),"embedding_model":"","ensure_paths":lambda:os.makedirs(os.path.join(tmp,"files"),exist_ok=True)})
    cfg.ensure_paths(); return tmp, db, cfg

def test_load():
    L = ModuleLoader(); m = L.load(_p()); assert m.name == "storage_manager"; L.cleanup(); print("✓ load")
def test_entry_points():
    L = ModuleLoader(); m = L.load(_p()); assert "classes.StorageManager" in m.entry_points; L.cleanup(); print("✓ entry_points")
def test_ingest():
    L = ModuleLoader() if 1 else None
    L=ModuleLoader(); m=L.load(_p()); SM=m.entry_points["classes.StorageManager"]
    tmp,db,cfg=setup(); sm=SM(db,None); sm.config=cfg; sm.classifier.config=cfg
    p=os.path.join(tmp,"a.py"); open(p,"w").write("x=1")
    iid=sm.ingest_file(p); assert iid is not None
    assert db.get_item(iid) is not None
    shutil.rmtree(tmp,ignore_errors=True); L.cleanup(); print("✓ ingest")
def test_dedup():
    L=ModuleLoader(); m=L.load(_p()); SM=m.entry_points["classes.StorageManager"]
    tmp,db,cfg=setup(); sm=SM(db,None); sm.config=cfg; sm.classifier.config=cfg
    p=os.path.join(tmp,"d.py"); open(p,"w").write("dedup")
    i1=sm.ingest_file(p); i2=sm.ingest_file(p)
    assert i1 is not None and i2 is None
    shutil.rmtree(tmp,ignore_errors=True); L.cleanup(); print("✓ dedup")
def test_delete():
    L=ModuleLoader(); m=L.load(_p()); SM=m.entry_points["classes.StorageManager"]
    tmp,db,cfg=setup(); sm=SM(db,None); sm.config=cfg; sm.classifier.config=cfg
    p=os.path.join(tmp,"del.py"); open(p,"w").write("delete")
    iid=sm.ingest_file(p); assert sm.delete_item(iid) is True
    shutil.rmtree(tmp,ignore_errors=True); L.cleanup(); print("✓ delete")
def test_hooks():
    L=ModuleLoader(); m=L.load(_p()); assert callable(m.instance.plugin_load); assert callable(m.instance.plugin_unload); L.cleanup(); print("✓ hooks")
if __name__=="__main__":
    for t in [test_load,test_entry_points,test_ingest,test_dedup,test_delete,test_hooks]:
        try: t()
        except Exception as e: import traceback; print(f"✗ {t.__name__}: {e}"); traceback.print_exc()
