# TheDevourer 开发日志

> 大嘴怪桌面小宠物 — 从想法到成品

---

## v1.0.0 — 2026-05-09

### 项目起源

灵感来源于 Karpathy 的 **llm-wiki** 思想：把本地文件当作可被 LLM 检索推理的个人知识库。结合桌面宠物的趣味交互形式，打造一个「投喂即知识」的工具——拖拽文件给精灵吃掉，自动分类归档，再用自然语言提问。

### 技术选型

| 方案 | 选择 | 理由 |
|------|------|------|
| GUI 框架 | **PySide6** | Python 生态、透明无边框窗口、拖放事件、QThread |
| 数据库 | **SQLite + FTS5** | 零配置、内建全文索引、触发器同步 |
| 向量存储 | **ChromaDB** | 轻量、纯 Python、持久化本地 |
| 嵌入模型 | **sentence-transformers** | 384 维、90MB、CPU 可跑 |
| 文件监听 | **watchdog** | 跨平台、事件驱动 |
| 文档解析 | **python-docx / openpyxl / PyPDF2 / python-pptx** | 覆盖主流 Office 格式 |
| 打包 | **PyInstaller** | 单 exe，用户无需 Python |

**排除的方案**：
- Electron/Tauri：太重（>200MB）、开发成本高、Python 文档解析生态无法复用
- C++ Qt：学习成本高、开发速度慢
- Java/Swing：跨平台差、UI 过时

### 架构设计

#### 三阶段设计

```
投喂闭环（功能性） → 知识库大脑（RAG） → 打磨交付（动画+打包）
```

每个阶段优先保证功能完整，再迭代优化体验。

#### 核心数据流

```
用户拖拽 → FeedHandler(队列) → FileClassifier(类型识别)
    → ContentClassifier(分类) → StorageManager(入库+FTS5)
    → watchdog(监听) → ChromaDB(向量索引) → KbQA(RAG问答)
```

#### RAG 检索链路

```
用户问题
  │
  ├─ FTS5 关键词搜索（BM25 排序）
  ├─ ChromaDB 语义搜索（余弦相似度）
  │     │
  │     └─ 合并去重（取最高分）
  │
  ├─ _build_context → [来源1] {文件名} \n {片段}
  ├─ _build_citation → 📚 引用来源列表
  │
  └─ LLM 流式推理（Ollama / OpenAI API）
        → 流式 token 回显到 QuestionDialog
```

#### 双引擎搜索策略

| 引擎 | 优劣 | 适用场景 |
|------|------|---------|
| FTS5 | 快、精确、无外部依赖 | 关键词精确匹配 |
| ChromaDB | 语义理解、对同义词有效 | 自然语言模糊查询 |
| 混合 | 两者结合取交集并集 | 通用搜索 |

### 数据模型

**核心表 `content_items` 设计要点**：

- `checksum`（MD5）作为去重键
- `embedding_status` 追踪向量索引状态（pending/indexing/done/failed/skipped）
- `text_content` 存储提取的纯文本，供 FTS5 和 ChromaDB 共用
- `category` 采用路径格式（如「文档/代码」「网址/技术」），支持无限层级

**FTS5 同步方案**：AFTER INSERT/DELETE/UPDATE 三个触发器保持主表和 FTS5 虚拟表同步。

### 测试策略

**测试覆盖率**：100 条测试覆盖全部 10 个核心模块。

| 模块 | 用例 | 测试方法 |
|------|------|---------|
| Config | 10 | 纯逻辑，mock QSettings |
| Database | 11 | 临时 SQLite，验证 CRUD |
| ChromaClient | 6 | mock ChromaDB 纯 Python 模拟 |
| Logger | 5 | 临时日志文件验证 |
| FeedHandler | 10 | mock 剪贴板/HTTP |
| FileClassifier | 15 | 6 种真实文件+4 边界 |
| ContentClassifier | 15 | 扩展名/域名/关键词/DB加载 |
| StorageManager | 12 | 全链路：入库→搜索→删除 |
| FileWatcher | 8 | 直接调用事件处理器+真实 watchdog |
| KbQA | 8 | FTS5 检索+对话历史+空库 |

### 踩坑记录

#### 1. numpy 跨版本冲突（耗时最长）

**现象**：Python 3.12 venv 加载 Python 3.10 的 numpy .so 文件时崩溃。

**原因**：numpy 的 C 扩展编译时绑定了 Python 版本号，跨版本加载失败。

**解决方案**：将所有依赖 ChromaDB/numpy 的模块改为**延迟导入**（lazy import），使核心模块在无 ChromaDB 时仍可测试。

**教训**：使用 venv 时，依赖必须全部在 venv 内安装，不能依赖系统 site-packages。

#### 2. inotify watch limit 限制

**现象**：watchdog 连续启动多个 Observer 时，报 "inotify watch limit reached"。

**原因**：Linux 系统 inotify 监控数有限（默认 8192），测试中未及时释放 Observer。

**解决方案**：每个测试完成后 `observer.stop()` + `observer.join()`，测试中遇到 inotify 错误时优雅跳过。

#### 3. PySide6 测试困境

**现象**：测试环境没有 PySide6，导致 `from PySide6.QtCore import QThread` 等导入失败。

**解决方案**：在 feed_handler.py 和 config.py 中实现 PySide6 的**延迟导入**，并提供了 Mock QThread/Mock QMimeData/Mock Signal 类，使非 GUI 逻辑可单独测试。

#### 4. UI 渲染策略

**设计决策**：精灵窗口使用 `WindowStaysOnTopHint | FramelessWindowHint | Tool`，配合 `WA_TranslucentBackground` 和 `WA_ShowWithoutActivating`，确保：
- 透明无边框显示
- 不抢前台应用输入焦点
- 不在任务栏显示
- 始终置顶

### 交互设计

#### 大嘴怪状态机

```
      idle（待机呼吸）
         │
   拖入文件/URL
         ▼
     hungry（张嘴）
         │
    识别完成
         ▼
     eating（咀嚼）
         │
     ┌──┴──┐
     │     │
   happy  error
   （开心）（摇头）
     │     │
     └──┬──┘
        │
      idle
```

#### 投喂交互流

```
拖入 → 气泡「📥 已收到：xxx」→ 张嘴动画 → 咀嚼动画
    → 气泡「📄 已归档 → 文档/代码」→ 开心动画 → 待机
```

### 待办事项

- [ ] **音视频转录**：集成 whisper.cpp，提取语音内容用于检索
- [ ] **网页完整存档**：SingleFile 保存完整 HTML，而非仅 URL
- [ ] **多语言 OCR**：PaddleOCR 提升中文/多语言识别准确率
- [ ] **标签自动补全**：基于已有标签的语义相似度推荐
- [ ] **浏览器扩展**：一键投喂当前网页
- [ ] **GitHub Releases**：CI/CD 自动构建 exe
- [ ] **正式精灵素材**：替换占位色块图为专业美术资源
- [ ] **macOS/Linux 支持**：验证跨平台兼容性
