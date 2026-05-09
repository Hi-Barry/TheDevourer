# 🦖 TheDevourer — 桌面知识管家

> 投喂即知识。拖拽任何内容给大嘴怪，它会吃掉、分类、索引，然后你可以用自然语言向它提问。

---

## ✨ 功能一览

| 功能 | 说明 |
|------|------|
| 🎯 **拖拽投喂** | 拖文件/文件夹/URL/截图到精灵身上，直接吃掉 |
| 📋 **剪贴板投喂** | 复制内容 → 右键「投喂剪贴板」 |
| 🤖 **自动分类** | 60+ 扩展名映射、30+ 域名识别、50+ 关键词标签 |
| 📚 **知识库 RAG** | FTS5 全文检索 + ChromaDB 向量语义搜索 + LLM 流式问答 |
| 🧠 **多 LLM 后端** | Ollama 本地 / OpenAI 兼容 API 任意切换 |
| 🔍 **内容浏览器** | 分类树浏览、关键词搜索、双击打开原文件 |
| 🎨 **精灵动画** | 6 状态帧动画（待机/张嘴/咀嚼/开心/思考/摇头） |
| 🪟 **系统托盘** | 托盘图标、开机自启、最小化到托盘 |
| 📦 **单 exe 打包** | PyInstaller 打包，无需 Python 环境 |

---

## 🚀 快速开始

### 方式一：直接运行 exe

1. 下载 `TheDevourer.exe`（见 Releases）
2. 双击运行，系统托盘出现 🦖 图标
3. 拖一个文件或网址给精灵 → 自动分类 → 双击精灵浏览仓库

### 方式二：源码运行

```bash
git clone https://github.com/Hi-Barry/TheDevourer.git
cd TheDevourer

python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
python main.py
```

### 知识库问答前置（可选）

```bash
# 本地 LLM（推荐）
ollama pull qwen2.5:7b

# 或在设置中切换为 OpenAI 兼容 API
# 右键 → 设置 → LLM → openai_compatible → 填入 API Key
```

---

## 🧪 测试

```bash
python -m pytest tests/ -v
```

当前 **100 条测试全部通过**，覆盖全部 10 个核心模块。

---

## 🏗️ 技术栈

| 层 | 选型 | 说明 |
|----|------|------|
| GUI | **PySide6** | Qt for Python，透明无边框窗口 |
| 数据库 | **SQLite** + **FTS5** | 全文索引，触发器同步 |
| 向量存储 | **ChromaDB** | 语义搜索，384 维嵌入 |
| 文件监听 | **watchdog** | 实时监听仓库变化 |
| 文件识别 | **python-magic** + **Pillow** | MIME 类型 + 图片元数据 |
| 文档解析 | **python-docx / openpyxl / PyPDF2 / python-pptx** | Office 文档全文提取 |
| LLM 推理 | **Ollama** / **OpenAI API** | 本地或远程推理 |
| 嵌入模型 | **sentence-transformers** | all-MiniLM-L6-v2 |
| 打包 | **PyInstaller** | 单 exe 分发 |

---

## 📁 项目结构

```
TheDevourer/
├── core/                  # 核心引擎
│   ├── config.py          # 配置管理（QSettings）
│   ├── db.py              # SQLite + FTS5 数据库
│   ├── chroma_client.py   # ChromaDB 向量客户端
│   ├── feed_handler.py    # 投喂队列（拖拽/粘贴/URL）
│   ├── file_classifier.py # 文件类型识别 + 元数据提取
│   ├── content_classifier.py # 规则分类引擎
│   ├── storage_manager.py # 存储 + 双引擎搜索
│   ├── file_watcher.py    # 文件监听 + 自动索引
│   ├── kb_qa.py           # RAG 知识库问答
│   └── logger.py          # 日志模块
├── ui/                    # 界面组件
│   ├── pet_window.py      # 精灵悬浮窗
│   ├── feed_bubble.py     # 投喂反馈气泡
│   ├── sprite_animator.py # 帧动画引擎
│   ├── question_dialog.py # 知识库提问界面
│   ├── content_browser.py # 内容浏览器
│   └── settings_dialog.py # 设置对话框
├── resources/             # 资源文件
│   ├── pet_idle.png       # 精灵占位图
│   └── anim/              # 6 状态帧动画
│       ├── idle/          # 待机（4 帧）
│       ├── hungry/        # 张嘴（3 帧）
│       ├── eating/        # 咀嚼（5 帧）
│       ├── happy/         # 开心（3 帧）
│       ├── thinking/      # 思考（4 帧）
│       └── error/         # 摇头（3 帧）
├── memory/                # 千语的运行日志
├── tests/                 # pytest 测试套件
│   ├── conftest.py        # 共享 fixtures
│   ├── test_config.py     # 10 条 ✅
│   ├── test_db.py         # 11 条 ✅
│   ├── test_chroma_client.py # 6 条 ✅
│   ├── test_logger.py     # 5 条 ✅
│   ├── test_feed_handler.py  # 10 条 ✅
│   ├── test_file_classifier.py # 15 条 ✅
│   ├── test_content_classifier.py # 15 条 ✅
│   ├── test_storage_manager.py # 12 条 ✅
│   ├── test_file_watcher.py # 8 条 ✅
│   └── test_kb_qa.py      # 8 条 ✅
├── DESIGN.md              # 功能设计文档
├── MODELS.md              # 数据模型文档
├── INSTALL.md             # 安装说明
├── README.md              # 本文件
├── requirements.txt       # Python 依赖
└── main.py                # 程序入口
```

---

## ⚙️ 投喂 → 知识库 全链路

```
拖拽文件/粘贴URL
    │
    ▼
FileClassifier       ← python-magic + Pillow + python-docx + PyPDF2
    │
    ▼
ContentClassifier    ← 扩展名/域名/关键词 规则分类
    │
    ▼
StorageManager       ← SQLite 入库 + FTS5 索引 + MD5 去重
    │
    ▼
watchdog 监听        ← 仓库文件变化自动触发向量化
    │
    ▼
ChromaDB             ← sentence-transformers 嵌入 + 语义索引
    │
    ▼
用户提问 ──→ KbQA ──→ _retrieve(混合搜索) ──→ _build_context ──→ LLM 流式回答
```

---

## 📜 许可证

MIT License © 2026 Hi-Barry
