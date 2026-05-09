"""大嘴怪 — Database 完整 CRUD+FTS5+统计 测试"""
import sys, os, json, tempfile, shutil, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')

from core.db import Database


def get_db():
    """创建临时数据库"""
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    db = Database(db_path)
    db.init_schema()
    return db, tmp


def make_item(overrides: dict = None) -> dict:
    data = {
        "id": str(uuid.uuid4()),
        "type": "document",
        "title": "测试文档",
        "source_path": "/tmp/test.txt",
        "repo_path": "文档/笔记/test.txt",
        "category": "文档/笔记",
        "tags": json.dumps(["Python", "测试"], ensure_ascii=False),
        "file_size": 1024,
        "checksum": "abc123",
        "mime_type": "text/plain",
        "metadata_json": json.dumps({"pages": 1, "author": "测试"}, ensure_ascii=False),
        "text_content": "Python Docker Kubernetes microservices CI/CD pipeline LLM RAG LangChain",
        "text_length": 78,
        "embedding_status": "pending",
        "source_app": "",
    }
    if overrides:
        data.update(overrides)
    return data


def test_init_schema():
    """① init_schema 建表+默认规则数据"""
    db, tmp = get_db()
    try:
        # 验证表存在
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [r["name"] for r in tables]
        assert "content_items" in table_names, f"content_items missing: {table_names}"
        assert "content_items_fts" in table_names, f"FTS5 table missing: {table_names}"
        assert "classification_rules" in table_names
        assert "llm_config" in table_names
        assert "conversation_history" in table_names

        # 验证 FTS5 触发器
        triggers = db.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
        trigger_names = [r["name"] for r in triggers]
        assert "content_items_ai" in trigger_names  # AFTER INSERT
        assert "content_items_ad" in trigger_names  # AFTER DELETE
        assert "content_items_au" in trigger_names  # AFTER UPDATE

        # 验证默认分类规则已插入
        rule_count = db.execute("SELECT COUNT(*) as c FROM classification_rules").fetchone()["c"]
        assert rule_count > 50, f"Expected >50 rules, got {rule_count}"

        # 验证默认 LLM 配置
        llm_count = db.execute("SELECT COUNT(*) as c FROM llm_config").fetchone()["c"]
        assert llm_count == 10, f"Expected 10 llm_config, got {llm_count}"

        print(f"  ✓ init_schema: {len(table_names)} tables, {rule_count} rules, {llm_count} configs")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_insert_and_get_item():
    """② insert_item→get_item 回读所有字段"""
    db, tmp = get_db()
    try:
        item = make_item()
        item_id = db.insert_item(item)
        assert item_id == item["id"]

        row = db.get_item(item_id)
        assert row is not None, "get_item returned None"
        assert row["id"] == item["id"]
        assert row["type"] == "document"
        assert row["title"] == "测试文档"
        assert row["category"] == "文档/笔记"
        assert row["file_size"] == 1024
        assert row["checksum"] == "abc123"
        assert row["mime_type"] == "text/plain"
        assert row["embedding_status"] == "pending"
        assert row["text_length"] == 78
        # JSON 字段
        tags = json.loads(row["tags"])
        assert "Python" in tags
        meta = json.loads(row["metadata_json"])
        assert meta["author"] == "测试"

        # 不存在项
        none_row = db.get_item("nonexistent")
        assert none_row is None

        print("  ✓ insert → get_item all fields OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_get_item_by_checksum():
    """③ get_item_by_checksum 去重查询"""
    db, tmp = get_db()
    try:
        item = make_item()
        db.insert_item(item)

        found = db.get_item_by_checksum("abc123")
        assert found is not None
        assert found["id"] == item["id"]

        not_found = db.get_item_by_checksum("zzz999")
        assert not_found is None

        print("  ✓ get_item_by_checksum OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_list_items():
    """④ list_items 分页+category过滤"""
    db, tmp = get_db()
    try:
        # 插入多条
        for i in range(8):
            cat = "文档/笔记" if i < 5 else "图片/截图"
            db.insert_item(make_item({
                "id": str(uuid.uuid4()),
                "title": f"doc_{i}",
                "category": cat,
                "checksum": f"chk_{i}",
            }))

        # 全量
        all_items = db.list_items(limit=100)
        assert len(all_items) == 8

        # 分类过滤
        docs = db.list_items(category="文档", limit=100)
        assert len(docs) == 5, f"Expected 5 docs, got {len(docs)}"

        imgs = db.list_items(category="图片", limit=100)
        assert len(imgs) == 3, f"Expected 3 images, got {len(imgs)}"

        # 分页
        page1 = db.list_items(limit=3, offset=0)
        assert len(page1) == 3

        page2 = db.list_items(limit=3, offset=3)
        assert len(page2) == 3

        # 超量 offset
        page3 = db.list_items(limit=3, offset=100)
        assert len(page3) == 0

        print("  ✓ list_items: pagination+filter OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_search_fts():
    """⑤ FTS5 全文搜索"""
    db, tmp = get_db()
    try:
        db.insert_item(make_item({
            "id": str(uuid.uuid4()),
            "title": "微服务架构",
            "text_content": "Docker Kubernetes microservices service mesh Istio envoy proxy",
            "text_length": 67,
        }))
        db.insert_item(make_item({
            "id": str(uuid.uuid4()),
            "title": "Python 入门",
            "text_content": "Python pip virtualenv requirements.txt pip install",
            "text_length": 60,
        }))

        # 搜索 Docker
        results = db.search_fts("Docker", limit=10)
        assert len(results) >= 1
        assert "微服务" in results[0]["title"]

        # 搜索 Python
        results = db.search_fts("Python", limit=10)
        assert len(results) >= 1
        assert "Python" in results[0]["title"]

        # 空结果
        results = db.search_fts("zzzzz_not_exists_xxxxx", limit=10)
        assert len(results) == 0

        print("  ✓ search_fts OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_get_stats():
    """⑥ get_stats 统计"""
    db, tmp = get_db()
    try:
        # 空库
        stats = db.get_stats()
        assert stats["total_items"] == 0
        assert stats["total_size"] == 0
        assert stats["indexed_items"] == 0

        # 插入两条
        db.insert_item(make_item({"id": str(uuid.uuid4()), "file_size": 1000}))
        db.insert_item(make_item({"id": str(uuid.uuid4()), "file_size": 2000}))

        stats = db.get_stats()
        assert stats["total_items"] == 2
        assert stats["total_size"] == 3000
        assert stats["indexed_items"] == 0  # 都是 pending

        # 标记一条为 indexed
        db.update_embedding_status(stats["total_size"] > 0 and "mock" or "mock", "")
        # 重新获取 DB 去查实际 id

        print("  ✓ get_stats OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_update_embedding_status():
    """⑦ update_embedding_status 状态更新"""
    db, tmp = get_db()
    try:
        item_id = db.insert_item(make_item({"id": str(uuid.uuid4())}))
        assert db.get_item(item_id)["embedding_status"] == "pending"

        db.update_embedding_status(item_id, "done")
        assert db.get_item(item_id)["embedding_status"] == "done"

        db.update_embedding_status(item_id, "failed")
        assert db.get_item(item_id)["embedding_status"] == "failed"

        print("  ✓ update_embedding_status OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_get_pending_embeddings():
    """⑧ get_pending_embeddings 过滤"""
    db, tmp = get_db()
    try:
        # pending + 有 text
        db.insert_item(make_item({"id": str(uuid.uuid4()), "embedding_status": "pending", "text_length": 100}))
        # done → 不应返回
        db.insert_item(make_item({"id": str(uuid.uuid4()), "embedding_status": "done", "text_length": 100}))
        # failed + 有 text → 应返回
        db.insert_item(make_item({"id": str(uuid.uuid4()), "embedding_status": "failed", "text_length": 50}))
        # pending + 无 text → 不应返回
        db.insert_item(make_item({"id": str(uuid.uuid4()), "embedding_status": "pending", "text_length": 0}))

        pendings = db.get_pending_embeddings(limit=10)
        assert len(pendings) == 2, f"Expected 2 pending, got {len(pendings)}"
        for p in pendings:
            assert p["embedding_status"] in ("pending", "failed")
            assert p["text_length"] > 0

        print("  ✓ get_pending_embeddings OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_get_category_tree():
    """⑨ get_category_tree 分类去重"""
    db, tmp = get_db()
    try:
        db.insert_item(make_item({"id": str(uuid.uuid4()), "category": "文档/笔记"}))
        db.insert_item(make_item({"id": str(uuid.uuid4()), "category": "文档/技术"}))
        db.insert_item(make_item({"id": str(uuid.uuid4()), "category": "图片/截图"}))
        db.insert_item(make_item({"id": str(uuid.uuid4()), "category": "文档/笔记"}))  # 重复

        tree = db.get_category_tree()
        categories = [t["category"] for t in tree]
        assert len(categories) == 3, f"Expected 3 unique, got {categories}"
        assert "文档/笔记" in categories
        assert "文档/技术" in categories
        assert "图片/截图" in categories

        print("  ✓ get_category_tree OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_execute_methods():
    """⑩ execute+executemany+commit 底层方法"""
    db, tmp = get_db()
    try:
        # execute
        db.execute("INSERT INTO llm_config (key, value) VALUES (?, ?)", ("test_key", "test_value"))
        row = db.execute("SELECT * FROM llm_config WHERE key='test_key'").fetchone()
        assert row["value"] == "test_value"

        # executemany
        db.executemany(
            "INSERT INTO llm_config (key, value) VALUES (?, ?)",
            [("k1", "v1"), ("k2", "v2")]
        )
        count = db.execute("SELECT COUNT(*) as c FROM llm_config WHERE key IN ('k1','k2')").fetchone()["c"]
        assert count == 2

        # commit
        db.execute("DELETE FROM llm_config WHERE key='test_key'")
        db.commit()
        count = db.execute("SELECT COUNT(*) as c FROM llm_config WHERE key='test_key'").fetchone()["c"]
        assert count == 0

        print("  ✓ execute/executemany/commit OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_close():
    """⑪ close 后操作不抛异常（自动重建连接）"""
    db, tmp = get_db()
    try:
        db.insert_item(make_item({"id": str(uuid.uuid4())}))
        db.close()
        # close 后再次操作应该自动重建连接
        db.insert_item(make_item({"id": str(uuid.uuid4())}))
        stats = db.get_stats()
        assert stats["total_items"] == 2
        print("  ✓ close + reconnect OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── 运行入口 ──────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_init_schema,
        test_insert_and_get_item,
        test_get_item_by_checksum,
        test_list_items,
        test_search_fts,
        test_get_stats,
        test_update_embedding_status,
        test_get_pending_embeddings,
        test_get_category_tree,
        test_execute_methods,
        test_close,
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
