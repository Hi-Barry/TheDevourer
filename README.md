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
├── core/                  # 核心层（内置，不可拆分）
│   ├── config.py          # 配置管理（QSettings）
│   ├── db.py              # SQLite + FTS5 数据库
│   ├── logger.py          # 日志模块
│   ├── signal_bus.py      # 信号总线（模块间通信）
│   ├── manifest_validator.py  # manifest.json 校验器
│   ├── module_loader.py   # 插件模块加载器
│   ├── chroma_client.py   # ChromaDB 向量客户端（内置）
│   ├── feed_handler.py    # 投喂队列
│   ├── file_classifier.py # 文件类型识别
│   ├── content_classifier.py # 规则分类引擎
│   ├── storage_manager.py # 存储 + 双引擎搜索
│   ├── file_watcher.py    # 文件监听
│   └── kb_qa.py           # RAG 知识库问答
├── modules/               # 可独立打包的功能模块
│   ├── feed_handler/      # 投喂处理（manifest + __init__）
│   ├── file_classifier/   # 文件类型识别
│   ├── content_classifier/ # 内容分类
│   ├── storage_manager/   # 存储引擎
│   ├── chroma_client/     # 向量客户端
│   ├── file_watcher/      # 文件监听
│   ├── kb_qa/             # 知识库问答
│   ├── ui_pet_window/     # 精灵悬浮窗
│   ├── ui_content_browser/ # 内容浏览器
│   ├── ui_question_dialog/ # 提问对话框
│   ├── ui_settings_dialog/ # 设置对话框
│   └── ui_tray/           # 系统托盘
├── plugins/               # 打包后的 .zip 模块（运行期加载）
│   ├── updates/           # 新版本模块
│   └── backups/           # 升级备份
├── tools/                 # 构建工具
│   └── pack_module.py     # 模块独立打包脚本
├── outputs/               # 模块打包产物
│   └── *.zip + *.sha256
├── resources/             # 资源文件
│   ├── pet_idle.png
│   └── anim/              # 6 状态帧动画（22 帧）
├── tests/                 # 测试套件（28 个文件，≥180 条）
│   ├── test_config.py             # Config 全属性  ✅
│   ├── test_db.py                 # 数据库 CRUD  ✅
│   ├── test_chroma_client.py      # 向量客户端  ✅
│   ├── test_logger.py             # 日志模块  ✅
│   ├── test_feed_handler.py       # 投喂逻辑  ✅
│   ├── test_file_classifier.py    # 文件识别  ✅
│   ├── test_content_classifier.py # 内容分类  ✅
│   ├── test_storage_manager.py    # 存储引擎  ✅
│   ├── test_file_watcher.py       # 文件监听  ✅
│   ├── test_kb_qa.py              # 知识库问答  ✅
│   ├── test_signal_bus.py         # 信号总线  ✅
│   ├── test_manifest.py           # manifest 校验  ✅
│   ├── test_module_loader.py      # 加载器  ✅
│   ├── test_main_launcher.py      # 启动链  ✅
│   ├── test_pack_module.py        # 打包脚本  ✅
│   ├── test_upgrade.py            # 热升级  ✅
│   ├── test_plugin_feed_handler.py       ✅
│   ├── test_plugin_file_classifier.py    ✅
│   ├── test_plugin_content_classifier.py ✅
│   ├── test_plugin_storage_manager.py    ✅
│   ├── test_plugin_chroma_client.py      ✅
│   ├── test_plugin_file_watcher.py       ✅
│   ├── test_plugin_kb_qa.py             ✅
│   ├── test_plugin_ui_pet_window.py     ✅
│   ├── test_plugin_ui_content_browser.py ✅
│   ├── test_plugin_ui_question_dialog.py ✅
│   ├── test_plugin_ui_settings_dialog.py ✅
│   └── test_plugin_ui_tray.py           ✅
├── DESIGN.md / MODELS.md / PLUGIN_ARCH.md  # 设计文档
├── INSTALL.md / README.md / DEVELOPMENT_LOG.md
├── requirements.txt
└── main.py                # 轻量启动器
```
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
