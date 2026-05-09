# 大嘴怪桌面小宠物 — 功能设计文档

> 版本：v1.0 | 不含视觉/动画设计，纯功能架构

---

## 1. 投喂入口与处理路径

### 1.1 投喂通道矩阵

| 通道 | 触发方式 | 内容类型 | 处理差异 |
|------|---------|---------|---------|
| 文件拖入 | 拖拽文件到精灵窗口 | 任意文件/文件夹 | 原始文件路径 → FileClassifier |
| 剪贴板粘贴 | Ctrl+V 到精灵窗口 / 托盘菜单 | 文件路径列表 / 图片 / 文本 / HTML | 根据 MIME 类型分流 |
| URL 粘贴 | 粘贴含 http(s):// 的文本 | 网址 | URL 识别 → title 抓取 → 归入「网址」类 |
| 截图粘贴 | 粘贴剪贴板中的位图 | 图片 (PNG/BMP) | 保存为 PNG → OCR 提取文字 → 归入「截图」类 |

### 1.2 投喂处理流水线

```
投喂入口（任一通道）
    │
    ├─ 文件/文件夹？──→ 遍历文件列表 → 逐个入投喂队列
    │
    ├─ 图片数据（剪贴板位图）？──→ 保存为 PNG → 作为文件处理
    │
    ├─ URL 文本？──→ URL 解析验证 → 抓取标题 → 作为 URL 记录
    │
    └─ 普通文本？──→ 保存为 .txt → 作为文件处理

投喂队列（QThread 后台线程）
    │
    for each item:
        ├─ 1. 计算 MD5 → 查重
        ├─ 2. FileClassifier.identify() → FileInfo
        ├─ 3. ContentClassifier.classify(FileInfo) → (category_path, tags)
        ├─ 4. StorageManager.ingest(FileInfo, category_path, tags) → item_id
        ├─ 5. 发出信号 → UI 更新气泡
        └─ 6. 发出信号 → watchdog 感知（自动触发索引）
```

---

## 2. 仓库目录结构

```
{用户指定仓库根目录}/
├── big_mouth.db                    # SQLite 主数据库
├── chroma_db/                      # ChromaDB 向量存储
├── files/                          # 内容文件归档
│   ├── 网址/
│   │   ├── 技术/
│   │   ├── 新闻/
│   │   ├── 社交/
│   │   ├── 视频/
│   │   └── 其他/
│   ├── 文档/
│   │   ├── PDF/
│   │   ├── Word/
│   │   ├── Excel/
│   │   ├── PPT/
│   │   ├── 代码/
│   │   ├── 笔记/
│   │   └── 其他/
│   ├── 图片/
│   │   ├── 截图/
│   │   ├── 照片/
│   │   ├── 设计/
│   │   └── 其他/
│   ├── 音视频/
│   │   ├── 音频/
│   │   └── 视频/
│   └── 其他/
├── .thumbnails/                    # 缩略图缓存
└── config.yaml                     # 用户配置（可选覆盖）
```

文件命名规则：`{uuid8}_{原文件名}`，UUID 截取前 8 位避免路径过长。

---

## 3. 分类规则体系

### 3.1 大类映射（扩展名 → 大类）

基于 `config/classification_rules.yaml` 配置，内置默认规则：

```yaml
categories:
  文档:
    extensions: [pdf, doc, docx, xls, xlsx, ppt, pptx, txt, md, rst, csv, json, xml, yaml, yml]
    mime_prefixes: [text/, application/pdf, application/msword, application/vnd.openxmlformats, application/vnd.ms-]
  图片:
    extensions: [png, jpg, jpeg, gif, bmp, webp, svg, ico, tiff, psd, ai]
    mime_prefixes: [image/]
  音视频:
    extensions: [mp3, wav, flac, aac, ogg, wma, mp4, avi, mkv, mov, wmv, flv, webm, m4a, m4v]
    mime_prefixes: [audio/, video/]
  压缩包:
    extensions: [zip, rar, 7z, tar, gz, bz2, xz]
    mime_prefixes: [application/zip, application/x-rar, application/x-7z, application/gzip]
  网址:
    virtual: true  # 虚拟分类，不依赖文件扩展名
```

### 3.2 子分类规则

```yaml
subcategories:
  文档:
    PDF:     {extensions: [pdf]}
    Word:    {extensions: [doc, docx]}
    Excel:   {extensions: [xls, xlsx, csv]}
    PPT:     {extensions: [ppt, pptx]}
    代码:    {extensions: [py, js, ts, java, go, rs, c, cpp, h, sh, sql, html, css, yaml, yml, json, xml, toml]}
    笔记:    {extensions: [md, rst, txt]}
  网址:
    技术:    {domains: [github.com, stackoverflow.com, gitlab.com, docs.python.org, *.dev, *.io]}
    新闻:    {domains: [news.ycombinator.com, *.news.cn, infoq.cn, 36kr.com, ithome.com]}
    社交:    {domains: [twitter.com, x.com, reddit.com, weibo.com, zhihu.com, juejin.cn]}
    AI研究:  {domains: [arxiv.org, paperswithcode.com, huggingface.co, openai.com, anthropic.com]}
```

### 3.3 标签自动生成

```yaml
tag_rules:
  - keywords: [python, django, flask, fastapi, pytorch, numpy, pandas]
    tag: Python
  - keywords: [javascript, typescript, react, vue, node, npm, nextjs]
    tag: 前端
  - keywords: [docker, kubernetes, k8s, devops, ci/cd, jenkins, github actions]
    tag: DevOps
  - keywords: [llm, gpt, transformer, rag, embedding, langchain, prompt]
    tag: AI/LLM
  - keywords: [linux, bash, shell, ssh, nginx, apache]
    tag: 运维
  - keywords: [database, sql, mysql, postgresql, mongodb, redis]
    tag: 数据库
```

---

## 4. 知识库架构

### 4.1 整体架构

```
┌─────────────────────────────────────────────────────┐
│                    大嘴怪知识库                        │
├─────────────────────────────────────────────────────┤
│                                                       │
│  ┌──────────┐    ┌───────────┐    ┌──────────────┐  │
│  │ watchdog │───→│ Text      │───→│ Embedding    │  │
│  │ 文件监听  │    │ Extractor │    │ Generator    │  │
│  │          │    │ 文本提取   │    │ 向量生成     │  │
│  └──────────┘    └───────────┘    └──────┬───────┘  │
│                                          │           │
│  ┌──────────┐    ┌───────────┐    ┌──────▼───────┐  │
│  │ 用户提问  │───→│ Query     │───→│ ChromaDB     │  │
│  │          │    │ Embedding │    │ 向量检索     │  │
│  └──────────┘    └───────────┘    └──────┬───────┘  │
│                                          │           │
│  ┌──────────┐    ┌───────────┐    ┌──────▼───────┐  │
│  │ 流式回答  │←───│ LLM       │←───│ Prompt       │  │
│  │ +引用来源 │    │ Inference │    │ 拼装        │  │
│  └──────────┘    └───────────┘    └──────────────┘  │
│                                                       │
│  ┌──────────────────────────────────────────────────┐ │
│  │ SQLite (FTS5) ←── 混合搜索 ──→ ChromaDB (向量)   │ │
│  └──────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 4.2 文件监听流程

```
watchdog.Observer 启动
    │
    ├─ on_created(event) → 新文件 → 加入索引队列
    ├─ on_modified(event) → 修改文件 → 更新索引
    ├─ on_deleted(event) → 删除文件 → 清理 ChromaDB 记录 + 标记 SQLite
    └─ on_moved(event) → 重命名 → 更新路径

启动时：全量扫描仓库 → 对比 SQLite embedding_status → 补齐未索引项
```

### 4.3 文本提取策略

| 文件类型 | 提取方式 | 备选 |
|---------|---------|------|
| .txt .md .csv | 直接读取 UTF-8/GBK | chardet 检测编码 |
| .docx | python-docx | — |
| .pptx | python-pptx | — |
| .xlsx | openpyxl / pandas | — |
| .pdf | PyPDF2 / pdfplumber | OCR 回退（扫描版 PDF） |
| 图片 (png/jpg) | Tesseract OCR | PaddleOCR 备选 |
| 音视频 | 元数据提取 + 标记待转录 | whisper.cpp 后期集成 |

### 4.4 文本分块策略

```
原始文本
    │
    ├─ 按段落分割（\\n\\n）
    │
    ├─ 若段落 > 500 字符 → RecursiveCharacterTextSplitter
    │      chunk_size=500, chunk_overlap=50
    │
    └─ 每个 chunk 标记来源（item_id + chunk_index）
```

### 4.5 向量存储

- **ChromaDB** 持久化存储（chroma_db/ 目录）
- 集合名：`big_mouth_kb`
- 元数据字段：`item_id`, `chunk_index`, `title`, `category`, `tags`, `file_path`
- 嵌入模型：`sentence-transformers/all-MiniLM-L6-v2`（384 维，90MB）

### 4.6 混合搜索

```
search(query, top_k=10):
    │
    ├─ FTS5 关键词搜索 → fts5_results（BM25 排序）
    │
    ├─ ChromaDB 语义搜索 → vector_results（余弦相似度排序）
    │
    ├─ 结果去重合并（按 item_id 去重，保留最高分）
    │
    └─ 返回 top_k 合并结果
```

---

## 5. LLM RAG 问答流程

```
用户输入问题
    │
    ├─ 1. 问题嵌入 → query_vector
    │
    ├─ 2. ChromaDB.similarity_search(query_vector, k=8)
    │      → 8 个最相关文档 chunks
    │
    ├─ 3. 按照 item_id 聚合 chunks → 去重 → 按相关性排序
    │
    ├─ 4. 组装 System Prompt:
    │       "你是大嘴怪，用户的私人知识管家。
    │        基于以下用户收藏的内容回答问题。
    │        如果知识库中没有相关信息，诚实告知。
    │        回答时注明引用的来源文件。"
    │
    ├─ 5. 组装 Context:
    │       [来源: {title} ({file_path})]
    │       {chunk_text}
    │       ---
    │       [来源: ...]
    │       ...
    │
    ├─ 6. LLM 流式推理（SSE/stream）
    │       ↓
    │   实时更新气泡中的回答文本
    │
    └─ 7. 回答末尾自动追加引用来源列表
```

### 5.1 LLM 后端支持

| 后端 | 配置 | 优点 | 缺点 |
|------|------|------|------|
| Ollama 本地 | endpoint: `http://localhost:11434` | 隐私、免费 | 需 GPU，模型大 |
| OpenAI 兼容 API | endpoint + api_key | 快、不占本地资源 | 需联网、付费 |

模型推荐：Qwen2.5-7B-Instruct（Ollama）或 deepseek-chat（API）。

---

## 6. 窗口与交互设计（功能层面）

### 6.1 精灵窗口状态

| 状态 | 触发 | 行为 |
|------|------|------|
| 待机 (idle) | 默认 | 显示精灵静态图，等待投喂 |
| 接收 (receiving) | 检测到拖拽悬停 | 窗口高亮/变大，提示可投喂 |
| 处理中 (processing) | 投喂确认后 | 队列工作中，显示进度 |
| 思考中 (thinking) | LLM 问答中 | 显示思考状态 |
| 完成 (done) | 处理完成 | 气泡提示结果 |

### 6.2 右键菜单

```
┌─────────────────┐
│ 投喂剪贴板       │
│ 提问...          │
│ 打开仓库         │
│ ─────────────── │
│ 设置...          │
│ 关于             │
│ 退出             │
└─────────────────┘
```

---

## 7. 技术债务与后续迭代

| 优先级 | 项目 | 说明 |
|--------|------|------|
| P1 | 音视频转录 | 集成 whisper.cpp，提取语音内容用于检索 |
| P2 | 网页完整存档 | SingleFile 存完整 HTML，而非仅标题+URL |
| P3 | 多语言 OCR | PaddleOCR 提升中文/多语言识别准确率 |
| P4 | 标签自动补全 | 基于已有标签的语义相似度推荐标签 |
| P5 | 浏览器扩展 | 一键投喂当前网页，无需复制 URL |
