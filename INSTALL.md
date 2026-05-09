# 大嘴怪 — 安装与使用说明

> 🦖 桌面知识管家 — 投喂即知识

---

## 环境要求

- **操作系统**：Windows 10/11（64位）
- **内存**：≥ 4GB RAM（知识库嵌入模型占用约 500MB）
- **硬盘**：≥ 500MB 可用空间（不含仓库内容）
- **GPU**：可选，Ollama 本地推理推荐 NVIDIA GPU（≥4GB VRAM）

## 快速安装

### 方式一：直接运行 exe（推荐）

1. 下载 `大嘴怪.exe`
2. 双击运行。首次启动自动创建仓库目录 `%USERPROFILE%/大嘴怪仓库/`
3. 系统托盘出现 🦖 图标，桌面右下角显示大嘴怪精灵

### 方式二：从源码运行

```bash
# 1. 安装 Python 3.10+
# 2. 克隆项目
git clone https://github.com/Hi-Barry/big-mouth-monster.git
cd big-mouth-monster

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行
python main.py
```

## 功能使用

### 投喂内容

| 方式 | 操作 |
|------|------|
| 拖拽文件 | 将文件/文件夹拖到大嘴怪身上 |
| 粘贴 URL | 复制网址 → 右键大嘴怪 → 投喂剪贴板 |
| 粘贴文本 | 复制文字 → 右键大嘴怪 → 投喂剪贴板 |
| 粘贴截图 | 截图到剪贴板 → 右键大嘴怪 → 投喂剪贴板 |

投喂后大嘴怪会张嘴咀嚼 → 自动分类归档 → 吐气泡显示结果。

### 浏览仓库

- **双击大嘴怪** → 打开内容浏览器
- 左侧分类树浏览，顶部搜索栏过滤
- 双击条目打开原文件

### 知识库问答

1. **右键大嘴怪** → 提问...
2. 输入问题，例如「我上周收藏的微服务文章说了什么？」
3. 大嘴怪从已投喂内容检索 → LLM 流式生成答案

**本地 LLM 设置**：
```bash
# 安装 Ollama
# 下载模型
ollama pull qwen2.5:7b
# 默认端点: http://localhost:11434
```

**远程 API 设置**：
右键 → 设置 → LLM 标签页 → 选择 openai_compatible → 填入 API 地址和 Key

---

## 打包构建

```bash
# Windows 环境
pip install pyinstaller
pyinstaller 大嘴怪.spec

# 输出: dist/大嘴怪.exe
```

目标体积：≤ 300MB（PySide6 ~100MB + 嵌入模型 ~90MB + ChromaDB ~30MB + 资源 ~10MB）

---

## 仓库目录结构

```
~/大嘴怪仓库/
├── big_mouth.db          # SQLite 数据库
├── chroma_db/            # ChromaDB 向量存储
├── logs/                 # 运行日志
├── files/                # 内容文件归档
│   ├── 网址/
│   ├── 文档/
│   ├── 图片/
│   ├── 音视频/
│   └── 其他/
└── .thumbnails/          # 缩略图缓存
```

---

## 常见问题

**Q: 拖拽没反应？**
A: 确保大嘴怪窗口在最前（右键任务栏 → 显示精灵）。

**Q: Ollama 连接失败？**
A: 确认 Ollama 已启动（`ollama serve`），端口 11434 未被占用。

**Q: 知识库问答说「没有相关内容」？**
A: 先投喂一些文档/网址到大嘴怪。知识库需要内容才能回答。

**Q: 开机自启如何关闭？**
A: 右键大嘴怪 → 设置 → 取消「开机自动启动」。

---

## 许可

MIT License
