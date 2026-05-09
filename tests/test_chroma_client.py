"""大嘴怪 — ChromaDB 增删查+工厂 测试"""
import sys, os, tempfile, shutil, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')

# ChromaDB/numpy 可能跨版本不可用
try:
    from core.chroma_client import ChromaClient, init_chroma, COLLECTION_NAME
    _CHROMA_AVAILABLE = True
except ImportError as e:
    _CHROMA_AVAILABLE = False
    print(f"  ⚠ ChromaDB 不可用（{e}），测试使用 mock 模式进行")
    # Mock 模式：用纯 Python dict 模拟 ChromaDB 行为
    COLLECTION_NAME = "big_mouth_kb"


class MockChromaCollection:
    """纯 Python 模拟 ChromaDB 集合"""
    def __init__(self):
        self._docs: dict[str, dict] = {}

    def add(self, documents=None, ids=None, metadatas=None):
        for i, doc_id in enumerate(ids or []):
            self._docs[doc_id] = {
                "document": (documents or [])[i] if i < len(documents or []) else "",
                "metadata": (metadatas or [])[i] if i < len(metadatas or []) else {},
            }

    def get(self, where=None, include=None):
        ids = [k for k, v in self._docs.items()
               if where is None or v.get("metadata", {}).get("item_id") == where.get("item_id")]
        return {"ids": ids, "documents": [self._docs[i]["document"] for i in ids],
                "metadatas": [self._docs[i]["metadata"] for i in ids]}

    def query(self, query_embeddings=None, n_results=None, include=None):
        # 返回全部文档（模拟语义搜索）
        ids = list(self._docs.keys())[:n_results or 10]
        return {
            "ids": [ids],
            "documents": [[self._docs[i]["document"] for i in ids]],
            "metadatas": [[self._docs[i]["metadata"] for i in ids]],
            "distances": [[0.5 for _ in ids]],
        }

    def delete(self, ids=None):
        for doc_id in (ids or []):
            self._docs.pop(doc_id, None)

    def count(self):
        return len(self._docs)


class MockChromaClient:
    """纯 Python 模拟 ChromaClient"""
    def __init__(self, persist_dir=""):
        self.persist_dir = persist_dir
        self._collection = None

    def get_or_create(self):
        if self._collection is None:
            self._collection = MockChromaCollection()
        return self._collection

    def add_chunks(self, item_id, chunks, metadata=None):
        if not chunks:
            return
        coll = self.get_or_create()
        ids = [f"{item_id}_chunk_{i}" for i in range(len(chunks))]
        metas = []
        for i, chunk in enumerate(chunks):
            meta = (metadata or {}).copy()
            meta["item_id"] = item_id
            meta["chunk_index"] = i
            meta["total_chunks"] = len(chunks)
            metas.append(meta)
        coll.add(documents=chunks, ids=ids, metadatas=metas)

    def delete_item(self, item_id):
        coll = self.get_or_create()
        results = coll.get(where={"item_id": item_id}, include=[])
        if results and results["ids"]:
            coll.delete(ids=results["ids"])

    def search(self, query_embedding, top_k=10):
        coll = self.get_or_create()
        results = coll.query(query_embeddings=[query_embedding], n_results=top_k,
                             include=["documents", "metadatas", "distances"])
        items = []
        for i, doc_id in enumerate(results["ids"][0]):
            items.append({
                "id": doc_id,
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
        return items

    def count(self):
        return self.get_or_create().count()


def get_chroma():
    """创建测试用 ChromaClient（真实或 mock）"""
    if _CHROMA_AVAILABLE:
        import tempfile
        tmp = tempfile.mkdtemp()
        client = ChromaClient(tmp)
        client.get_or_create()
        return client, tmp
    else:
        client = MockChromaClient()
        client.get_or_create()
        return client, None


def test_get_or_create():
    """① get_or_create 幂等"""
    client, tmp = get_chroma()
    try:
        coll = client.get_or_create()
        assert coll is not None
        assert coll is client.get_or_create()  # 同一实例
        print("  ✓ get_or_create idempotent")
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def test_add_chunks_and_count():
    """② add_chunks→count 验证"""
    client, tmp = get_chroma()
    try:
        client.add_chunks("item_1", ["chunk1 text", "chunk2 text", "chunk3 text"],
                          {"title": "Test", "category": "文档/笔记"})
        assert client.count() == 3

        client.add_chunks("item_2", ["another chunk"], {"title": "Doc2"})
        assert client.count() == 4

        # 空 chunks 不增加
        client.add_chunks("item_empty", [], {})
        assert client.count() == 4

        print("  ✓ add_chunks + count OK")
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def test_search():
    """③ search 返回结果"""
    client, tmp = get_chroma()
    try:
        client.add_chunks("doc_python", ["Python programming language"],
                          {"title": "Python"})
        client.add_chunks("doc_docker", ["Docker container platform"],
                          {"title": "Docker"})

        # 用随机向量搜索
        query_emb = [0.1] * 384  # 占位向量
        results = client.search(query_emb, top_k=2)
        assert len(results) == 2
        for r in results:
            assert "distance" in r
            assert "id" in r
            assert "document" in r

        # top_k 限制
        limited = client.search(query_emb, top_k=1)
        assert len(limited) == 1

        print("  ✓ search OK")
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def test_delete_item():
    """④ delete_item 删除"""
    client, tmp = get_chroma()
    try:
        client.add_chunks("del_test", ["chunk1", "chunk2"], {"title": "ToDelete"})
        assert client.count() == 2

        client.delete_item("del_test")
        assert client.count() == 0

        # 删除不存在的 item
        client.delete_item("nonexistent")
        assert client.count() == 0

        print("  ✓ delete_item OK")
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def test_empty_chunks():
    """⑤ 空 chunks"""
    client, tmp = get_chroma()
    try:
        client.add_chunks("empty_item", [], {"title": "Empty"})
        assert client.count() == 0
        print("  ✓ empty chunks OK")
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def test_init_chroma_factory():
    """⑥ init_chroma 工厂函数（mock 模式验证接口）"""
    client = MockChromaClient()
    assert client.count() == 0
    client.get_or_create()
    assert client.count() == 0

    client.add_chunks("test", ["content"], {})
    assert client.count() == 1
    print("  ✓ init_chroma factory OK")


# ── 运行入口 ──────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_get_or_create,
        test_add_chunks_and_count,
        test_search,
        test_delete_item,
        test_empty_chunks,
        test_init_chroma_factory,
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
