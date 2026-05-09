"""大嘴怪 — 数据库模块

管理 SQLite 连接、建表、CRUD 操作。
"""
import sqlite3
import json
import threading
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime

# ── 建表 DDL ──────────────────────────────────────

SCHEMA_SQL = """
-- 内容主表
CREATE TABLE IF NOT EXISTS content_items (
    id              TEXT PRIMARY KEY,
    type            TEXT NOT NULL DEFAULT 'other',
    title           TEXT NOT NULL DEFAULT '',
    source_path     TEXT,
    source_url      TEXT,
    repo_path       TEXT NOT NULL DEFAULT '',
    category        TEXT NOT NULL DEFAULT '其他',
    tags            TEXT NOT NULL DEFAULT '[]',
    file_size       INTEGER NOT NULL DEFAULT 0,
    checksum        TEXT NOT NULL DEFAULT '',
    mime_type       TEXT NOT NULL DEFAULT '',
    metadata_json   TEXT NOT NULL DEFAULT '{}',
    text_content    TEXT NOT NULL DEFAULT '',
    text_length     INTEGER NOT NULL DEFAULT 0,
    embedding_status TEXT NOT NULL DEFAULT 'pending',
    thumbnail_path  TEXT,
    source_app      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- FTS5 全文索引
CREATE VIRTUAL TABLE IF NOT EXISTS content_items_fts USING fts5(
    title,
    tags,
    text_content,
    content='content_items',
    content_rowid='rowid'
);

-- FTS5 触发器
CREATE TRIGGER IF NOT EXISTS content_items_ai AFTER INSERT ON content_items BEGIN
    INSERT INTO content_items_fts(rowid, title, tags, text_content)
    VALUES (new.rowid, new.title, new.tags, new.text_content);
END;

CREATE TRIGGER IF NOT EXISTS content_items_ad AFTER DELETE ON content_items BEGIN
    INSERT INTO content_items_fts(content_items_fts, rowid, title, tags, text_content)
    VALUES ('delete', old.rowid, old.title, old.tags, old.text_content);
END;

CREATE TRIGGER IF NOT EXISTS content_items_au AFTER UPDATE ON content_items BEGIN
    INSERT INTO content_items_fts(content_items_fts, rowid, title, tags, text_content)
    VALUES ('delete', old.rowid, old.title, old.tags, old.text_content);
    INSERT INTO content_items_fts(rowid, title, tags, text_content)
    VALUES (new.rowid, new.title, new.tags, new.text_content);
END;

-- 常用索引
CREATE INDEX IF NOT EXISTS idx_content_items_type ON content_items(type);
CREATE INDEX IF NOT EXISTS idx_content_items_category ON content_items(category);
CREATE INDEX IF NOT EXISTS idx_content_items_checksum ON content_items(checksum);
CREATE INDEX IF NOT EXISTS idx_content_items_created_at ON content_items(created_at);
CREATE INDEX IF NOT EXISTS idx_content_items_embedding_status ON content_items(embedding_status);

-- 分类规则表
CREATE TABLE IF NOT EXISTS classification_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_type   TEXT NOT NULL,
    category    TEXT NOT NULL,
    subcategory TEXT NOT NULL DEFAULT '',
    pattern     TEXT NOT NULL,
    priority    INTEGER NOT NULL DEFAULT 0,
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_classrule_type_pattern ON classification_rules(rule_type, pattern);

-- LLM 配置表
CREATE TABLE IF NOT EXISTS llm_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

-- 对话历史表
CREATE TABLE IF NOT EXISTS conversation_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    sources_json TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_conv_session ON conversation_history(session_id, created_at);
"""

# ── 默认分类规则数据 ───────────────────────────────

DEFAULT_RULES_SQL = """
INSERT OR IGNORE INTO classification_rules (rule_type, category, subcategory, pattern, priority) VALUES
    -- 扩展名 → 文档
    ('extension','文档','PDF','.pdf',5),
    ('extension','文档','Word','.docx',5),('extension','文档','Word','.doc',5),
    ('extension','文档','Excel','.xlsx',5),('extension','文档','Excel','.xls',5),
    ('extension','文档','PPT','.pptx',5),('extension','文档','PPT','.ppt',5),
    ('extension','文档','代码','.py',5),('extension','文档','代码','.js',5),
    ('extension','文档','代码','.ts',5),('extension','文档','代码','.java',5),
    ('extension','文档','代码','.go',5),('extension','文档','代码','.rs',5),
    ('extension','文档','代码','.cpp',5),('extension','文档','代码','.c',5),
    ('extension','文档','代码','.h',5),('extension','文档','代码','.html',5),
    ('extension','文档','代码','.css',5),('extension','文档','代码','.json',5),
    ('extension','文档','代码','.yaml',5),('extension','文档','代码','.yml',5),
    ('extension','文档','代码','.toml',5),('extension','文档','代码','.sql',5),
    ('extension','文档','代码','.sh',5),('extension','文档','笔记','.md',5),
    ('extension','文档','笔记','.rst',5),('extension','文档','笔记','.txt',5),
    ('extension','文档','其他','.csv',3),('extension','文档','其他','.xml',3),
    -- 扩展名 → 图片
    ('extension','图片','截图','.png',4),('extension','图片','截图','.jpg',4),
    ('extension','图片','截图','.jpeg',4),('extension','图片','截图','.gif',4),
    ('extension','图片','截图','.bmp',4),('extension','图片','截图','.webp',4),
    ('extension','图片','其他','.svg',3),('extension','图片','其他','.ico',3),
    -- 扩展名 → 音视频
    ('extension','音视频','音频','.mp3',5),('extension','音视频','音频','.wav',5),
    ('extension','音视频','音频','.flac',5),('extension','音视频','音频','.aac',5),
    ('extension','音视频','视频','.mp4',5),('extension','音视频','视频','.avi',5),
    ('extension','音视频','视频','.mkv',5),('extension','音视频','视频','.mov',5),
    ('extension','音视频','视频','.webm',5),
    -- 域名 → 网址
    ('domain','网址','技术','github.com',10),('domain','网址','技术','gitlab.com',10),
    ('domain','网址','技术','stackoverflow.com',10),('domain','网址','技术','docs.python.org',8),
    ('domain','网址','AI研究','arxiv.org',10),('domain','网址','AI研究','paperswithcode.com',10),
    ('domain','网址','AI研究','huggingface.co',10),('domain','网址','AI研究','openai.com',8),
    ('domain','网址','新闻','news.ycombinator.com',8),('domain','网址','新闻','infoq.cn',8),
    ('domain','网址','新闻','36kr.com',8),('domain','网址','新闻','ithome.com',8),
    ('domain','网址','社交','reddit.com',5),('domain','网址','社交','zhihu.com',5),
    ('domain','网址','社交','juejin.cn',5),('domain','网址','视频','youtube.com',8),
    ('domain','网址','视频','bilibili.com',8),
    -- 关键词 → 标签
    ('keyword','标签','Python','python',5),('keyword','标签','Python','django',5),
    ('keyword','标签','Python','flask',5),('keyword','标签','Python','fastapi',5),
    ('keyword','标签','Python','pytorch',5),('keyword','标签','Frontend','javascript',5),
    ('keyword','标签','Frontend','typescript',5),('keyword','标签','Frontend','react',5),
    ('keyword','标签','Frontend','vue',5),('keyword','标签','DevOps','docker',5),
    ('keyword','标签','DevOps','kubernetes',5),('keyword','标签','DevOps','ci/cd',5),
    ('keyword','标签','AI/LLM','llm',5),('keyword','标签','AI/LLM','gpt',5),
    ('keyword','标签','AI/LLM','transformer',5),('keyword','标签','AI/LLM','rag',5),
    ('keyword','标签','AI/LLM','langchain',5),('keyword','标签','AI/LLM','embedding',5),
    ('keyword','标签','Database','sql',5),('keyword','标签','Database','mysql',5),
    ('keyword','标签','Database','postgresql',5),('keyword','标签','Database','mongodb',5),
    ('keyword','标签','Database','redis',5),('keyword','标签','Linux','linux',5),
    ('keyword','标签','Linux','bash',5),('keyword','标签','Linux','nginx',5);
"""

DEFAULT_LLM_CONFIG_SQL = """
INSERT OR IGNORE INTO llm_config (key, value) VALUES
    ('llm_backend','ollama'),
    ('ollama_endpoint','http://localhost:11434'),
    ('ollama_model','qwen2.5:7b'),
    ('api_endpoint','https://api.openai.com/v1'),
    ('api_key',''),
    ('api_model','gpt-4o-mini'),
    ('embedding_model','all-MiniLM-L6-v2'),
    ('embedding_device','cpu'),
    ('max_context_chunks','8'),
    ('max_history_rounds','10');
"""


class Database:
    """SQLite 数据库管理器，线程安全"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()

    def _get_conn(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def init_schema(self) -> None:
        """初始化全部表结构 + 默认数据"""
        conn = self._get_conn()
        conn.executescript(SCHEMA_SQL)
        conn.executescript(DEFAULT_RULES_SQL)
        conn.executescript(DEFAULT_LLM_CONFIG_SQL)
        conn.commit()

    def execute(self, sql: str, params=None):
        """执行 SQL，返回 cursor"""
        conn = self._get_conn()
        return conn.execute(sql, params or ())

    def executemany(self, sql: str, params):
        conn = self._get_conn()
        return conn.executemany(sql, params)

    def commit(self):
        self._get_conn().commit()

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    # ── 内容 CRUD ──────────────────────────────────

    def insert_item(self, item_dict: dict) -> str:
        """插入一条内容记录，返回 id"""
        item_id = item_dict.get("id") or str(uuid.uuid4())
        item_dict["id"] = item_id
        columns = [
            "id", "type", "title", "source_path", "source_url", "repo_path",
            "category", "tags", "file_size", "checksum", "mime_type",
            "metadata_json", "text_content", "text_length", "embedding_status",
            "thumbnail_path", "source_app"
        ]
        placeholders = ", ".join("?" for _ in columns)
        col_names = ", ".join(columns)
        values = [item_dict.get(c, "") for c in columns]
        self.execute(
            f"INSERT INTO content_items ({col_names}) VALUES ({placeholders})",
            values
        )
        self.commit()
        return item_id

    def get_item(self, item_id: str) -> Optional[dict]:
        row = self.execute(
            "SELECT * FROM content_items WHERE id=?", (item_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_item_by_checksum(self, checksum: str) -> Optional[dict]:
        row = self.execute(
            "SELECT * FROM content_items WHERE checksum=?", (checksum,)
        ).fetchone()
        return dict(row) if row else None

    def list_items(self, category: str = None, type_: str = None,
                   limit: int = 100, offset: int = 0) -> list[dict]:
        sql = "SELECT * FROM content_items WHERE 1=1"
        params = []
        if category:
            sql += " AND category LIKE ?"
            params.append(f"{category}%")
        if type_:
            sql += " AND type=?"
            params.append(type_)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def search_fts(self, query: str, limit: int = 20) -> list[dict]:
        """FTS5 全文搜索"""
        rows = self.execute(
            """SELECT c.* FROM content_items c
               JOIN content_items_fts f ON c.rowid = f.rowid
               WHERE content_items_fts MATCH ?
               ORDER BY rank LIMIT ?""",
            (query, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    def update_embedding_status(self, item_id: str, status: str) -> None:
        self.execute(
            "UPDATE content_items SET embedding_status=?, updated_at=datetime('now','localtime') WHERE id=?",
            (status, item_id)
        )
        self.commit()

    def get_pending_embeddings(self, limit: int = 100) -> list[dict]:
        rows = self.execute(
            "SELECT * FROM content_items WHERE embedding_status IN ('pending','failed') AND text_length > 0 ORDER BY created_at LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_category_tree(self) -> list[dict]:
        """获取分类树（用于浏览器）"""
        rows = self.execute(
            "SELECT DISTINCT category FROM content_items ORDER BY category"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """获取仓库统计"""
        total = self.execute("SELECT COUNT(*) as cnt FROM content_items").fetchone()["cnt"]
        total_size = self.execute("SELECT COALESCE(SUM(file_size),0) as s FROM content_items").fetchone()["s"]
        indexed = self.execute(
            "SELECT COUNT(*) as cnt FROM content_items WHERE embedding_status='done'"
        ).fetchone()["cnt"]
        return {"total_items": total, "total_size": total_size, "indexed_items": indexed}
