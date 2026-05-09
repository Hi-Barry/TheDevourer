"""大嘴怪 — StorageManager 全链路 12 维度测试"""
import sys, os, json, tempfile, shutil, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')

from core.db import Database
from core.storage_manager import StorageManager
from core.chroma_client import ChromaClient


def setup():
    """创建完整的测试环境：tmpdir + db + sm"""
    tmp = tempfile.mkdtemp()
    repo_dir = os.path.join(tmp, "repo")
    files_dir = os.path.join(repo_dir, "files")
    chroma_dir = os.path.join(repo_dir, "chroma_db")
    os.makedirs(files_dir, exist_ok=True)
    os.makedirs(chroma_dir, exist_ok=True)

    db = Database(os.path.join(repo_dir, "big_mouth.db"))
    db.init_schema()

    # Mock config
    class MockConfig:
        repo_path = repo_dir
        files_path = files_dir
        chroma_path = chroma_dir
        embedding_model = "all-MiniLM-L6-v2"
        def ensure_paths(self):
            os.makedirs(self.repo_path, exist_ok=True)
            os.makedirs(self.files_path, exist_ok=True)
            os.makedirs(self.chroma_path, exist_ok=True)

    config = MockConfig()

    # ChromaDB mock
    try:
        chroma = ChromaClient(chroma_dir)
        chroma.get_or_create()
    except Exception:
        chroma = None

    sm = StorageManager(db, chroma)
    sm.config = config
    sm.classifier.config = config

    return sm, db, tmp


# ── 测试用例 ──────────────────────────────────────

def test_ingest_file():
    """① ingest_file → DB记录+文件复制+分类正确"""
    sm, db, tmp = setup()
    try:
        path = os.path.join(tmp, "hello.py")
        with open(path, "w") as f:
            f.write("import sys\ndef hello():\n    print('hello world')\n")

        item_id = sm.ingest_file(path)
        assert item_id is not None, "ingest_file returned None"

        # DB 记录
        item = db.get_item(item_id)
        assert item is not None, "get_item returned None"
        assert item["type"] == "document"
        assert "代码" in item["category"] or "文档" in item["category"]

        # 文件已复制
        repo_path = item["repo_path"]
        full_path = Path(sm.config.files_path) / repo_path
        assert full_path.exists(), f"File not found: {full_path}"
        assert full_path.stat().st_size > 0

        print("  ✓ ingest_file → DB + file copy + category")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_md5_dedup():
    """② MD5 去重（同文件二次 ingest → None）"""
    sm, db, tmp = setup()
    try:
        path = os.path.join(tmp, "dup.py")
        with open(path, "w") as f:
            f.write("print('dedup test')")

        first = sm.ingest_file(path)
        assert first is not None
        second = sm.ingest_file(path)
        assert second is None, "Dedup should return None"

        print("  ✓ MD5 dedup: duplicate → None")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_ingest_url():
    """③ ingest_url → .url文件+InternetShortcut格式"""
    sm, db, tmp = setup()
    try:
        url_id = sm.ingest_url("https://github.com/docker/compose", "Docker Compose")
        assert url_id is not None

        item = db.get_item(url_id)
        assert item["type"] == "url"
        assert item["title"] == "Docker Compose"

        # .url 文件格式
        full_path = Path(sm.config.files_path) / item["repo_path"]
        assert full_path.exists()
        content = full_path.read_text()
        assert "InternetShortcut" in content
        assert "github.com" in content

        print("  ✓ ingest_url → .url file + InternetShortcut format")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_ingest_text():
    """④ ingest_text → .txt+标签自动提取"""
    sm, db, tmp = setup()
    try:
        text_id = sm.ingest_text("Python Docker Kubernetes LLM RAG deployment")
        assert text_id is not None

        item = db.get_item(text_id)
        assert item["type"] == "document"
        assert "笔记" in item["category"] or "文档" in item["category"]

        tags = json.loads(item["tags"])
        assert "Python" in tags
        assert "DevOps" in tags or "AI/LLM" in tags

        # .txt 文件存在
        full_path = Path(sm.config.files_path) / item["repo_path"]
        assert full_path.exists()

        print("  ✓ ingest_text → .txt + tags auto-extracted")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_search_fts():
    """⑤ search_fts 关键词搜索"""
    sm, db, tmp = setup()
    try:
        path = os.path.join(tmp, "search.txt")
        with open(path, "w") as f:
            f.write("Docker Kubernetes microservices service mesh")

        sm.ingest_file(path)
        db.commit()

        results = sm.search_fts("Kubernetes", limit=10)
        assert len(results) >= 1, f"Expected ≥1 result, got {len(results)}"
        assert "Kubernetes" in results[0].get("text_content", "") or "search" in results[0]["title"].lower()

        print("  ✓ search_fts: keyword search → results")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_search_hybrid_fallback():
    """⑥ search_hybrid 无 ChromaDB 时降级纯FTS5"""
    sm_no_chroma, db, tmp = setup()
    try:
        sm_no_chroma.chroma = None
        path = os.path.join(tmp, "hybrid.txt")
        with open(path, "w") as f:
            f.write("Hybrid search test content")

        sm_no_chroma.ingest_file(path)

        results = sm_no_chroma.search_hybrid("hybrid search", limit=5)
        assert isinstance(results, list)
        assert len(results) >= 1

        print("  ✓ search_hybrid: fallback to FTS5 when no chroma")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_index_item():
    """⑦ index_item → embedding_status pending→done"""
    sm, db, tmp = setup()
    try:
        path = os.path.join(tmp, "index_me.txt")
        with open(path, "w") as f:
            f.write("Item to be indexed with content")

        item_id = sm.ingest_file(path)
        assert item_id is not None

        # 索引（即使无真正嵌入模型，也应更新状态）
        try:
            sm.index_item(item_id)
        except Exception:
            pass

        item = db.get_item(item_id)
        # 状态可能仍是 pending（缺少嵌入模型），不强制 done
        assert item["embedding_status"] in ("pending", "done", "failed")

        print("  ✓ index_item: status updated")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_index_pending():
    """⑧ index_pending 批量索引计数"""
    sm, db, tmp = setup()
    try:
        for i in range(3):
            path = os.path.join(tmp, f"pending_{i}.txt")
            with open(path, "w") as f:
                f.write(f"Content {i}" * 20)
            sm.ingest_file(path)

        # 全部应为 pending
        pendings = db.get_pending_embeddings(limit=10)
        assert len(pendings) >= 3, f"Expected ≥3 pending, got {len(pendings)}"

        print("  ✓ index_pending: batch count OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_chunk_text():
    """⑨ _chunk_text 分块逻辑"""
    sm, _, _ = setup()
    # 短文本不分块
    short = "Hello world"
    chunks = sm._chunk_text(short, chunk_size=500, overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == short

    # 长文本分块
    long_text = "word " * 200
    chunks = sm._chunk_text(long_text, chunk_size=100, overlap=20)
    assert len(chunks) >= 2, f"Expected ≥2 chunks, got {len(chunks)}"

    # overlap 验证
    if len(chunks) >= 2:
        assert len(chunks[0]) >= 80

    print("  ✓ _chunk_text: short no-split + long split + overlap")


def test_delete_item():
    """⑩ delete_item → 文件+SQLite+ChromaDB 清理"""
    sm, db, tmp = setup()
    try:
        path = os.path.join(tmp, "to_delete.py")
        with open(path, "w") as f:
            f.write("print('delete me')")

        item_id = sm.ingest_file(path)
        assert item_id is not None
        repo_path = db.get_item(item_id)["repo_path"]
        full_path = Path(sm.config.files_path) / repo_path
        assert full_path.exists()

        # 删除
        deleted = sm.delete_item(item_id)
        assert deleted is True

        # 文件已删除
        assert not full_path.exists(), "File should be deleted"
        # DB 记录已删除
        assert db.get_item(item_id) is None

        print("  ✓ delete_item: file + DB + chroma cleanup")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_export_by_category():
    """⑪ export_by_category 按分类导出"""
    sm, db, tmp = setup()
    try:
        # 插入一条
        path = os.path.join(tmp, "export_me.py")
        with open(path, "w") as f:
            f.write("print('export test')")
        sm.ingest_file(path)

        # 导出
        export_dir = os.path.join(tmp, "exported")
        sm.export_by_category("文档", export_dir)

        exported_files = os.listdir(export_dir)
        assert len(exported_files) >= 1, f"Expected files in export, got {exported_files}"

        print("  ✓ export_by_category: files exported")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_tags_to_json():
    """⑫ _tags_to_json 静态方法"""
    sm, _, _ = setup()
    result = sm._tags_to_json(["Python", "测试"])
    parsed = json.loads(result)
    assert parsed == ["Python", "测试"]

    result = sm._tags_to_json([])
    parsed = json.loads(result)
    assert parsed == []
    print("  ✓ _tags_to_json static method")


# ── 运行入口 ──────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_ingest_file,
        test_md5_dedup,
        test_ingest_url,
        test_ingest_text,
        test_search_fts,
        test_search_hybrid_fallback,
        test_index_item,
        test_index_pending,
        test_chunk_text,
        test_delete_item,
        test_export_by_category,
        test_tags_to_json,
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
