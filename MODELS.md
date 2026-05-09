# 大嘴怪 — 数据模型设计文档

> 版本：v1.0 | SQLite + ChromaDB | 所有表位于 big_mouth.db

---

## 1. 核心表结构

### 1.1 content_items（内容主表）

```sql
CREATE TABLE IF NOT EXISTS content_items (
    id              TEXT PRIMARY KEY,           -- UUID4
    type            TEXT NOT NULL,              -- url / document / image / audio / video / archive / other
    title           TEXT NOT NULL DEFAULT '',   -- 标题（文件名去掉扩展名，或 URL title）
    source_path     TEXT,                        -- 原始文件路径（投喂时的路径，可能已不存在）
    source_url      TEXT,                        -- 原始 URL（URL 类型时使用）
    repo_path       TEXT NOT NULL,              -- 仓库内文件路径（相对仓库根目录）
    category        TEXT NOT NULL DEFAULT '其他',-- 分类路径，如「文档/PDF」
    tags            TEXT NOT NULL DEFAULT '[]',  -- JSON 数组字符串，如 ["Python", "AI"]
    file_size       INTEGER NOT NULL DEFAULT 0, -- 字节数
    checksum        TEXT NOT NULL DEFAULT '',   -- MD5（用于去重）
    mime_type       TEXT NOT NULL DEFAULT '',   -- MIME 类型
    metadata_json   TEXT NOT NULL DEFAULT '{}', -- 元数据 JSON（宽高/页数/时长/作者等）
    text_content    TEXT NOT NULL DEFAULT '',   -- 提取的文本内容全文（用于 FTS5 和分块）
    text_length     INTEGER NOT NULL DEFAULT 0, -- text_content 字符数
    embedding_status TEXT NOT NULL DEFAULT 'pending', -- pending / indexing / done / failed / skipped
    thumbnail_path  TEXT,                        -- 缩略图路径（可选）
    source_app      TEXT,                        -- 来源应用（可选，如 "Chrome", "WeChat"）
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- FTS5 全文索引
CREATE VIRTUAL TABLE IF NOT EXISTS content_items_fts USING fts5(
    title,
    tags,
    text_content,
    content='content_items',
    content_rowid='rowid'
);

-- 触发器：保持 FTS5 与主表同步
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
```

### 1.2 数据模型（Python dataclass）

```python
from dataclasses import dataclass, field
import uuid
import json
from datetime import datetime
from typing import Optional

@dataclass
class ContentItem:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = "other"          # url/document/image/audio/video/archive/other
    title: str = ""
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    repo_path: str = ""
    category: str = "其他"
    tags: list[str] = field(default_factory=list)
    file_size: int = 0
    checksum: str = ""
    mime_type: str = ""
    metadata_json: dict = field(default_factory=dict)
    text_content: str = ""
    text_length: int = 0
    embedding_status: str = "pending"  # pending/indexing/done/failed/skipped
    thumbnail_path: Optional[str] = None
    source_app: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "source_path": self.source_path,
            "source_url": self.source_url,
            "repo_path": self.repo_path,
            "category": self.category,
            "tags": json.dumps(self.tags, ensure_ascii=False),
            "file_size": self.file_size,
            "checksum": self.checksum,
            "mime_type": self.mime_type,
            "metadata_json": json.dumps(self.metadata_json, ensure_ascii=False),
            "text_content": self.text_content,
            "text_length": self.text_length,
            "embedding_status": self.embedding_status,
            "thumbnail_path": self.thumbnail_path,
            "source_app": self.source_app,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_db_row(cls, row: dict) -> "ContentItem":
        return cls(
            id=row["id"],
            type=row["type"],
            title=row["title"],
            source_path=row.get("source_path"),
            source_url=row.get("source_url"),
            repo_path=row.get("repo_path", ""),
            category=row.get("category", "其他"),
            tags=json.loads(row.get("tags", "[]")),
            file_size=row.get("file_size", 0),
            checksum=row.get("checksum", ""),
            mime_type=row.get("mime_type", ""),
            metadata_json=json.loads(row.get("metadata_json", "{}")),
            text_content=row.get("text_content", ""),
            text_length=row.get("text_length", 0),
            embedding_status=row.get("embedding_status", "pending"),
            thumbnail_path=row.get("thumbnail_path"),
            source_app=row.get("source_app"),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )
```

---

## 2. ChromaDB 向量存储模型

### 2.1 集合定义

```python
# 集合名
COLLECTION_NAME = "big_mouth_kb"

# 嵌入维度（all-MiniLM-L6-v2）
EMBEDDING_DIM = 384

# metadata schema（每个 chunk 携带的元数据）
chunk_metadata = {
    "item_id": str,       # content_items.id
    "chunk_index": int,   # 该 chunk 在文本中的序号（从 0 开始）
    "total_chunks": int,  # 该 item 总共的 chunk 数
    "title": str,         # 来源标题
    "category": str,      # 分类
    "tags": str,          # 标签（逗号分隔）
    "file_path": str,     # 仓库内文件路径
    "type": str,          # 文件类型
}

# ChromaDB 文档 ID 格式
doc_id = f"{item_id}_chunk_{chunk_index}"
```

### 2.2 分块参数

```python
CHUNK_SIZE = 500       # 每块最大字符数
CHUNK_OVERLAP = 50     # 块间重叠字符数
MIN_CHUNK_SIZE = 100   # 低于此尺寸不单独成块，合并到前一块
```

---

## 3. 分类规则配置

### 3.1 classification_rules 表

```sql
CREATE TABLE IF NOT EXISTS classification_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_type   TEXT NOT NULL,      -- 'extension', 'mime', 'domain', 'keyword'
    category    TEXT NOT NULL,      -- 大类名
    subcategory TEXT NOT NULL DEFAULT '', -- 子分类名
    pattern     TEXT NOT NULL,      -- 匹配模式（扩展名/域名/关键词）
    priority    INTEGER NOT NULL DEFAULT 0, -- 优先级（越大越优先）
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_classification_rules_pattern ON classification_rules(rule_type, pattern);
```

### 3.2 默认规则数据

```sql
-- 扩展名规则
INSERT INTO classification_rules (rule_type, category, subcategory, pattern, priority) VALUES
    ('extension', '文档', 'PDF',    '.pdf',       5),
    ('extension', '文档', 'Word',   '.docx',      5),
    ('extension', '文档', 'Word',   '.doc',       5),
    ('extension', '文档', 'Excel',  '.xlsx',      5),
    ('extension', '文档', 'Excel',  '.xls',       5),
    ('extension', '文档', 'PPT',    '.pptx',      5),
    ('extension', '文档', 'PPT',    '.ppt',       5),
    ('extension', '文档', '代码',   '.py',        5),
    ('extension', '文档', '代码',   '.js',        5),
    ('extension', '文档', '代码',   '.ts',        5),
    ('extension', '文档', '代码',   '.java',      5),
    ('extension', '文档', '代码',   '.go',        5),
    ('extension', '文档', '代码',   '.rs',        5),
    ('extension', '文档', '代码',   '.cpp',       5),
    ('extension', '文档', '代码',   '.c',         5),
    ('extension', '文档', '代码',   '.html',      5),
    ('extension', '文档', '代码',   '.css',       5),
    ('extension', '文档', '代码',   '.json',      5),
    ('extension', '文档', '代码',   '.yaml',      5),
    ('extension', '文档', '代码',   '.yml',       5),
    ('extension', '文档', '代码',   '.toml',      5),
    ('extension', '文档', '代码',   '.sql',       5),
    ('extension', '文档', '代码',   '.sh',        5),
    ('extension', '文档', '笔记',   '.md',        5),
    ('extension', '文档', '笔记',   '.rst',       5),
    ('extension', '文档', '笔记',   '.txt',       5),
    ('extension', '文档', '其他',   '.csv',       3),
    ('extension', '文档', '其他',   '.xml',       3),
    ('extension', '图片', '截图',   '.png',       4),
    ('extension', '图片', '截图',   '.jpg',       4),
    ('extension', '图片', '截图',   '.jpeg',      4),
    ('extension', '图片', '截图',   '.gif',       4),
    ('extension', '图片', '截图',   '.bmp',       4),
    ('extension', '图片', '截图',   '.webp',      4),
    ('extension', '图片', '其他',   '.svg',       3),
    ('extension', '图片', '其他',   '.ico',       3),
    ('extension', '图片', '其他',   '.psd',       3),
    ('extension', '音视频', '音频', '.mp3',       5),
    ('extension', '音视频', '音频', '.wav',       5),
    ('extension', '音视频', '音频', '.flac',      5),
    ('extension', '音视频', '音频', '.aac',       5),
    ('extension', '音视频', '音频', '.ogg',       5),
    ('extension', '音视频', '视频', '.mp4',       5),
    ('extension', '音视频', '视频', '.avi',       5),
    ('extension', '音视频', '视频', '.mkv',       5),
    ('extension', '音视频', '视频', '.mov',       5),
    ('extension', '音视频', '视频', '.webm',      5);

-- URL 域名规则
INSERT INTO classification_rules (rule_type, category, subcategory, pattern, priority) VALUES
    ('domain', '网址', '技术',  'github.com',        10),
    ('domain', '网址', '技术',  'gitlab.com',        10),
    ('domain', '网址', '技术',  'stackoverflow.com', 10),
    ('domain', '网址', '技术',  'docs.python.org',    8),
    ('domain', '网址', 'AI研究','arxiv.org',         10),
    ('domain', '网址', 'AI研究','paperswithcode.com',10),
    ('domain', '网址', 'AI研究','huggingface.co',    10),
    ('domain', '网址', 'AI研究','openai.com',         8),
    ('domain', '网址', '新闻',  'news.ycombinator.com', 8),
    ('domain', '网址', '新闻',  'infoq.cn',           8),
    ('domain', '网址', '新闻',  '36kr.com',           8),
    ('domain', '网址', '新闻',  'ithome.com',         8),
    ('domain', '网址', '社交',  'reddit.com',         5),
    ('domain', '网址', '社交',  'zhihu.com',          5),
    ('domain', '网址', '社交',  'juejin.cn',          5),
    ('domain', '网址', '视频',  'youtube.com',        8),
    ('domain', '网址', '视频',  'bilibili.com',       8);

-- 关键词标签规则
INSERT INTO classification_rules (rule_type, category, subcategory, pattern, priority) VALUES
    ('keyword', '标签', 'Python',     'python',       5),
    ('keyword', '标签', 'Python',     'django',       5),
    ('keyword', '标签', 'Python',     'flask',        5),
    ('keyword', '标签', 'Python',     'fastapi',      5),
    ('keyword', '标签', 'Python',     'pytorch',      5),
    ('keyword', '标签', 'Frontend',   'javascript',   5),
    ('keyword', '标签', 'Frontend',   'typescript',   5),
    ('keyword', '标签', 'Frontend',   'react',        5),
    ('keyword', '标签', 'Frontend',   'vue',          5),
    ('keyword', '标签', 'DevOps',     'docker',       5),
    ('keyword', '标签', 'DevOps',     'kubernetes',   5),
    ('keyword', '标签', 'DevOps',     'k8s',          5),
    ('keyword', '标签', 'DevOps',     'ci/cd',        5),
    ('keyword', '标签', 'AI/LLM',     'llm',          5),
    ('keyword', '标签', 'AI/LLM',     'gpt',          5),
    ('keyword', '标签', 'AI/LLM',     'transformer',  5),
    ('keyword', '标签', 'AI/LLM',     'rag',          5),
    ('keyword', '标签', 'AI/LLM',     'langchain',    5),
    ('keyword', '标签', 'AI/LLM',     'embedding',    5),
    ('keyword', '标签', 'Database',   'sql',          5),
    ('keyword', '标签', 'Database',   'mysql',        5),
    ('keyword', '标签', 'Database',   'postgresql',   5),
    ('keyword', '标签', 'Database',   'mongodb',      5),
    ('keyword', '标签', 'Database',   'redis',        5),
    ('keyword', '标签', 'Linux',      'linux',        5),
    ('keyword', '标签', 'Linux',      'bash',         5),
    ('keyword', '标签', 'Linux',      'nginx',        5),
    ('keyword', '标签', 'Linux',      'ssh',          5);
```

---

## 4. 配置表

### 4.1 llm_config

```sql
CREATE TABLE IF NOT EXISTS llm_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- 默认配置
INSERT OR IGNORE INTO llm_config (key, value) VALUES
    ('llm_backend',         'ollama'),          -- ollama | openai_compatible
    ('ollama_endpoint',     'http://localhost:11434'),
    ('ollama_model',        'qwen2.5:7b'),
    ('api_endpoint',        'https://api.openai.com/v1'),
    ('api_key',             ''),
    ('api_model',           'gpt-4o-mini'),
    ('embedding_model',     'all-MiniLM-L6-v2'),
    ('embedding_device',    'cpu'),             -- cpu | cuda
    ('max_context_chunks',  '8'),
    ('max_history_rounds',  '10');
```

### 4.2 app_config（运行时通过 QSettings 管理，此处记录键名）

```python
APP_CONFIG_KEYS = {
    # 通用
    "repo_path":            str,    # 仓库根目录，默认 ~/大嘴怪仓库
    "first_run":            bool,   # 是否首次运行
    "language":             str,    # zh / en

    # 窗口
    "window_x":             int,    # 精灵窗口 X 坐标
    "window_y":             int,    # 精灵窗口 Y 坐标
    "window_scale":         float,  # 精灵缩放比例，默认 1.0
    "always_on_top":        bool,   # 默认 True

    # 系统
    "autostart":            bool,   # 开机启动
    "minimize_to_tray":     bool,   # 关闭时最小化到托盘

    # 投喂
    "clipboard_monitor":    bool,   # 是否监听剪贴板
    "auto_classify":        bool,   # 投喂后自动分类

    # 知识库
    "auto_index":           bool,   # 投喂后自动索引
    "watchdog_enabled":     bool,   # 是否启用文件监听
}
```

---

## 5. 对话历史表

```sql
CREATE TABLE IF NOT EXISTS conversation_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,      -- 会话 ID（同一次对话的轮次属于同一 session）
    role        TEXT NOT NULL,      -- user / assistant / system
    content     TEXT NOT NULL,
    sources_json TEXT,               -- 该轮回答引用的来源（JSON）
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_conv_session ON conversation_history(session_id, created_at);
```

---

## 6. ChromaDB ↔ SQLite 对应关系

```
content_items 表                        ChromaDB
─────────────────────────────────       ──────────────────────────────
 id (TEXT)                        ←→    metadata["item_id"]
 title                            ←→    metadata["title"]
 category                         ←→    metadata["category"]
 tags                             ←→    metadata["tags"]
 repo_path                        ←→    metadata["file_path"]
 text_content ──分块──→           ←→    documents[] (n 个 chunk)
 embedding_status                  ←    跟踪字段（仅在 SQLite）
```

---

## 7. ER 图（文字版）

```
┌─────────────────┐     ┌──────────────────────┐
│  content_items  │     │ classification_rules  │
│─────────────────│     │──────────────────────│
│ id (PK)         │     │ id (PK)              │
│ type            │     │ rule_type            │
│ title           │     │ category             │
│ source_path     │     │ subcategory          │
│ source_url      │     │ pattern              │
│ repo_path       │     │ priority             │
│ category  ──────┼──┐  │ enabled              │
│ tags            │  │  └──────────────────────┘
│ file_size       │  │
│ checksum (UQ)   │  │  ┌──────────────────────┐
│ mime_type       │  │  │   llm_config         │
│ metadata_json   │  │  │──────────────────────│
│ text_content    │  │  │ key (PK)             │
│ text_length     │  │  │ value                │
│ embedding_status│  │  └──────────────────────┘
│ thumbnail_path  │  │
│ created_at      │  │  ┌──────────────────────┐
│ updated_at      │  │  │ conversation_history  │
└─────────────────┘  │  │──────────────────────│
       │             │  │ id (PK)              │
       │ FTS5        │  │ session_id           │
       ▼             │  │ role                 │
┌──────────────────┐ │  │ content              │
│ content_items_fts│ │  │ sources_json         │
└──────────────────┘ │  │ created_at           │
                      │  └──────────────────────┘
       ▲              │
       │ ChromaDB 映射│
       │              │
┌──────────────────┐  │
│   ChromaDB       │  │
│  big_mouth_kb    │  │
│──────────────────│  │
│ id: item_id_chunk│  │
│ document: chunk  │  │
│ embedding: 384d  │  │
│ metadata: {...}  │──┘
└──────────────────┘
```
