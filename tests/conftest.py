"""大嘴怪测试 — 共享 Fixtures

提供所有测试文件公用的临时目录、数据库、样例文件生成器等 fixtures。
"""
import os
import json
import uuid
import hashlib
from pathlib import Path
from typing import Callable
from io import BytesIO

import pytest
# PIL 在 fixture 内部延迟导入，避免跨版本 .so 冲突

# ── 将项目根目录加入 sys.path ─────────────────────
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── 临时目录 ──────────────────────────────────────

@pytest.fixture
def tmpdir() -> str:
    """创建临时目录，测试结束后自动清理"""
    import tempfile
    _dir = tempfile.mkdtemp(prefix="bigmouth_test_")
    yield _dir
    import shutil
    shutil.rmtree(_dir, ignore_errors=True)


# ── 数据库 ────────────────────────────────────────

@pytest.fixture
def db(tmpdir: str):
    """初始化 SQLite 数据库并建表"""
    from core.db import Database
    _db = Database(str(Path(tmpdir) / "test.db"))
    _db.init_schema()
    yield _db
    _db.close()


# ── Mock Config（不含 QSettings）─────────────────

@pytest.fixture
def mock_config(tmpdir: str):
    """提供不含 PySide6 QSettings 依赖的 Config 实例"""
    from core.config import Config
    cfg = Config()
    # 强制使用 dict 存储（防止 QSettings ImportError）
    cfg._use_qt = False
    cfg._store = {
        "repo_path": str(Path(tmpdir) / "repo"),
        "files_path": str(Path(tmpdir) / "repo" / "files"),
        "chroma_path": str(Path(tmpdir) / "repo" / "chroma_db"),
        "first_run": True,
        "language": "zh",
        "window_x": -1,
        "window_y": -1,
        "window_scale": 1.0,
        "always_on_top": True,
        "autostart": False,
        "minimize_to_tray": True,
        "clipboard_monitor": True,
        "auto_classify": True,
        "auto_index": True,
        "watchdog_enabled": True,
        "llm_backend": "ollama",
        "ollama_endpoint": "http://localhost:11434",
        "ollama_model": "qwen2.5:7b",
        "api_endpoint": "https://api.openai.com/v1",
        "api_key": "",
        "api_model": "gpt-4o-mini",
        "embedding_model": "all-MiniLM-L6-v2",
        "embedding_device": "cpu",
        "max_context_chunks": 8,
        "max_history_rounds": 10,
    }
    cfg._settings = type("MockSettings", (), {
        "value": lambda self, key, default=None: cfg._store.get(key, default),
        "setValue": lambda self, key, val: cfg._store.__setitem__(key, val),
        "sync": lambda self: None,
    })()
    cfg.ensure_paths()
    return cfg


# ── Mock ChromaDB ────────────────────────────────

@pytest.fixture
def mock_chroma(tmpdir: str):
    """内存模式 ChromaDB 客户端"""
    from core.chroma_client import ChromaClient
    persist_dir = str(Path(tmpdir) / "chroma_test")
    client = ChromaClient(persist_dir)
    client.get_or_create()
    return client


# ── 样例文件生成器 ───────────────────────────────

@pytest.fixture
def sample_files(tmpdir: str) -> dict[str, str]:
    """生成各类样例文件，返回 {描述: 路径} 字典"""
    files = {}

    # 1. Python 文件
    py_path = Path(tmpdir) / "hello.py"
    py_path.write_text("import sys\n\ndef greet(name: str) -> str:\n    return f'Hello, {name}!'\n\nif __name__ == '__main__':\n    print(greet('World'))\n")
    files["python"] = str(py_path)

    # 2. Markdown
    md_path = Path(tmpdir) / "readme.md"
    md_path.write_text("# Test\n\nThis is a **markdown** file.\n\n- Python is great\n- Docker is useful\n- LLM is the future\n")
    files["markdown"] = str(md_path)

    # 3. JSON
    json_path = Path(tmpdir) / "data.json"
    json_path.write_text(json.dumps({"name": "test", "version": 1, "tags": ["python", "docker"]}, indent=2))
    files["json"] = str(json_path)

    # 4. Plain text (UTF-8)
    txt_path = Path(tmpdir) / "note.txt"
    txt_path.write_text("Learning Python Docker Kubernetes microservices CI/CD pipeline LLM RAG LangChain")
    files["txt"] = str(txt_path)

    # 5. PNG 图片（200×200 纯色）
    png_path = Path(tmpdir) / "image.png"
    try:
        from PIL import Image
        img = Image.new("RGB", (200, 200), (100, 200, 100))
        img.save(str(png_path), "PNG")
    except ImportError:
        # 无PIL时创建纯文本占位
        png_path.write_text("(placeholder png)")
    files["png"] = str(png_path)

    # 6. Empty file
    empty_path = Path(tmpdir) / "empty.txt"
    empty_path.touch()
    files["empty"] = str(empty_path)

    # 7. ZIP 压缩包
    zip_path = Path(tmpdir) / "archive.zip"
    import zipfile
    with zipfile.ZipFile(str(zip_path), "w") as zf:
        zf.writestr("file1.txt", "content1")
        zf.writestr("file2.txt", "content2")
    files["zip"] = str(zip_path)

    # 8. 大文件（超过 10MB 边界测试）
    large_path = Path(tmpdir) / "large.bin"
    large_path.write_bytes(b"x" * (11 * 1024 * 1024))  # 11MB
    files["large"] = str(large_path)

    return files


# ── 辅助函数 ──────────────────────────────────────

def assert_file_exists(path: str) -> None:
    """断言文件存在"""
    assert os.path.isfile(path), f"文件不存在: {path}"


def assert_content_contains(path: str, substring: str) -> None:
    """断言文件内容包含某字符串"""
    content = Path(path).read_text()
    assert substring in content, f"文件内容不包含「{substring}」"
