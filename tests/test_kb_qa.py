"""大嘴怪 — KbQA 知识库问答 检索+上下文+引用+对话+工厂 测试"""
import sys, os, json, tempfile, shutil, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')

from core.db import Database
from core.kb_qa import KbQA, create_kb_qa


def setup():
    """创建测试环境：tmp + db + 插入样例数据"""
    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "test.db"))
    db.init_schema()

    # 插入 3 条测试内容
    from core.storage_manager import StorageManager
    from core.file_classifier import FileClassifier

    class MockConfig:
        repo_path = tmp
        files_path = os.path.join(tmp, "files")
        chroma_path = os.path.join(tmp, "chroma_db")
        embedding_model = "all-MiniLM-L6-v2"
        max_context_chunks = 8
        max_history_rounds = 10
        llm_backend = "ollama"
        ollama_endpoint = "http://localhost:11434"
        ollama_model = "qwen2.5:7b"
        api_endpoint = "https://api.openai.com/v1"
        api_key = ""
        api_model = "gpt-4o-mini"
        embedding_device = "cpu"
        def ensure_paths(self): pass

    cfg = MockConfig()
    os.makedirs(cfg.files_path, exist_ok=True)

    sm = StorageManager(db, None)
    sm.config = cfg
    sm.classifier.config = cfg

    # 创建 3 个测试文件并入库
    contents = {
        "docker_kubernetes.txt": "Docker and Kubernetes are container orchestration tools for microservices deployment.",
        "python_ai.txt": "Python is widely used for AI/LLM development with frameworks like PyTorch and LangChain.",
        "linux_ops.txt": "Linux system administration includes SSH Nginx Docker and Bash scripting.",
    }

    item_ids = {}
    for name, text in contents.items():
        path = os.path.join(tmp, name)
        with open(path, "w") as f:
            f.write(text)
        item_id = sm.ingest_file(path)
        item_ids[name] = item_id

    sm.index_pending(10)  # 索引处理（即使无嵌入模型，状态会更新）

    return db, cfg, sm, item_ids, tmp


def test_retrieve_fts():
    """① _retrieve FTS5 查询→含 item_id/title/snippet/score"""
    db, cfg, sm, ids, tmp = setup()
    try:
        kqa = KbQA(db, None)
        kqa.config = cfg

        sources = kqa._retrieve("Docker Kubernetes", top_k=5)
        assert len(sources) >= 1, f"Expected ≥1 source, got {len(sources)}"
        s = sources[0]
        assert "item_id" in s, f"Missing item_id: {s.keys()}"
        assert "title" in s
        assert "score" in s

        print(f"  ✓ _retrieve FTS5: {len(sources)} sources, keys={list(s.keys())}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_retrieve_empty():
    """② 空知识库→空列表"""
    tmp = tempfile.mkdtemp()
    try:
        db_empty = Database(os.path.join(tmp, "empty.db"))
        db_empty.init_schema()
        kqa = KbQA(db_empty, None)
        kqa.config = db_empty  # just pass something

        sources = kqa._retrieve("nonexistent topic xyz", top_k=5)
        # 无数据时返回空列表
        assert len(sources) == 0, f"Expected 0, got {len(sources)}"
        print("  ✓ _retrieve: empty KB → []")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_build_context():
    """③ _build_context 含[来源1]编号+文件路径+片段"""
    db, cfg, sm, ids, tmp = setup()
    try:
        kqa = KbQA(db, None)
        kqa.config = cfg

        sources = kqa._retrieve("Docker microservices", top_k=2)
        assert len(sources) >= 1

        context = kqa._build_context(sources)
        assert "[来源1]" in context or "[来源" in context
        assert len(context) > 10

        if len(sources) >= 2:
            assert "[来源2]" in context

        print(f"  ✓ _build_context: has source markers, length={len(context)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_build_citation():
    """④ _build_citation 📚格式含编号+标题+路径"""
    db, cfg, sm, ids, tmp = setup()
    try:
        kqa = KbQA(db, None)
        kqa.config = cfg

        sources = kqa._retrieve("Linux", top_k=2)
        assert len(sources) >= 1

        citation = kqa._build_citation(sources)
        assert "📚" in citation
        assert "1." in citation
        assert len(citation) > 20

        # 空来源返回空
        assert kqa._build_citation([]) == ""

        print(f"  ✓ _build_citation: has 📚 + numbering, empty→''")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_conversation():
    """⑤ save_conversation + get_conversation 读写完整"""
    db, cfg, sm, ids, tmp = setup()
    try:
        kqa = KbQA(db, None)
        kqa.config = cfg
        session_id = kqa.new_session()

        kqa.save_conversation(session_id, "user", "什么是微服务？")
        kqa.save_conversation(session_id, "assistant", "微服务是...", [{"title": "微服务架构", "score": 0.9}])

        history = kqa.get_conversation(session_id, limit=10)
        assert len(history) == 2

        assert history[0]["role"] == "user"
        assert history[0]["content"] == "什么是微服务？"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "微服务是..."

        # sources_json
        sources = json.loads(history[1]["sources_json"] or "[]")
        assert len(sources) == 1
        assert sources[0]["title"] == "微服务架构"

        print("  ✓ conversation: save → get → verify fields")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_new_session():
    """⑥ new_session → 两次调用返回不同 UUID"""
    db, cfg, sm, ids, tmp = setup()
    try:
        kqa = KbQA(db, None)
        kqa.config = cfg

        s1 = kqa.new_session()
        s2 = kqa.new_session()
        assert s1 != s2, "Sessions should be unique"
        # UUID 格式验证
        assert len(s1) == 36, f"Expected UUID length 36, got {len(s1)}"
        assert "-" in s1

        print("  ✓ new_session: unique UUIDs")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_ask_empty_kb():
    """⑦ ask 空知识库→提示语"""
    tmp = tempfile.mkdtemp()
    try:
        db_empty = Database(os.path.join(tmp, "empty.db"))
        db_empty.init_schema()
        kqa = KbQA(db_empty, None)
        kqa.config = type("cfg", (), {"max_context_chunks": 8, "max_history_rounds": 10,
                                        "llm_backend": "ollama", "ollama_endpoint": "",
                                        "api_endpoint": "", "api_key": "", "api_model": "",
                                        "embedding_model": "", "embedding_device": "cpu"})

        answer = kqa.ask("说说微服务架构")
        assert "还没吃过" in answer or "无法回答" in answer or "投喂" in answer

        print(f"  ✓ ask empty KB → '{answer[:50]}...'")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_create_kb_qa_factory():
    """⑧ create_kb_qa 返回 KbQA 实例"""
    db, cfg, sm, ids, tmp = setup()
    try:
        kqa = create_kb_qa(db, None)
        assert isinstance(kqa, KbQA)
        assert kqa.db is db
        print("  ✓ create_kb_qa factory → KbQA instance")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── 运行入口 ──────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_retrieve_fts,
        test_retrieve_empty,
        test_build_context,
        test_build_citation,
        test_conversation,
        test_new_session,
        test_ask_empty_kb,
        test_create_kb_qa_factory,
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
