"""大嘴怪 — 内容分类引擎

规则分类器：扩展名→大类 + 域名→子类 + 关键词→标签。
LLM 分类接口预留。
"""
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from core.file_classifier import FileInfo
from core.logger import get_logger

logger = get_logger()

# ── 扩展名 → 分类映射 ────────────────────────────

EXTENSION_CATEGORY = {
    # 文档
    ".pdf": ("文档", "PDF"),
    ".doc": ("文档", "Word"),
    ".docx": ("文档", "Word"),
    ".xls": ("文档", "Excel"),
    ".xlsx": ("文档", "Excel"),
    ".csv": ("文档", "Excel"),
    ".ppt": ("文档", "PPT"),
    ".pptx": ("文档", "PPT"),
    ".py": ("文档", "代码"),
    ".js": ("文档", "代码"),
    ".ts": ("文档", "代码"),
    ".jsx": ("文档", "代码"),
    ".tsx": ("文档", "代码"),
    ".java": ("文档", "代码"),
    ".go": ("文档", "代码"),
    ".rs": ("文档", "代码"),
    ".cpp": ("文档", "代码"),
    ".c": ("文档", "代码"),
    ".h": ("文档", "代码"),
    ".html": ("文档", "代码"),
    ".css": ("文档", "代码"),
    ".scss": ("文档", "代码"),
    ".sql": ("文档", "代码"),
    ".sh": ("文档", "代码"),
    ".bash": ("文档", "代码"),
    ".yaml": ("文档", "代码"),
    ".yml": ("文档", "代码"),
    ".json": ("文档", "代码"),
    ".xml": ("文档", "代码"),
    ".toml": ("文档", "代码"),
    ".ini": ("文档", "代码"),
    ".cfg": ("文档", "代码"),
    ".md": ("文档", "笔记"),
    ".rst": ("文档", "笔记"),
    ".txt": ("文档", "笔记"),
    ".log": ("文档", "笔记"),
    # 图片
    ".png": ("图片", "截图"),
    ".jpg": ("图片", "截图"),
    ".jpeg": ("图片", "截图"),
    ".gif": ("图片", "截图"),
    ".bmp": ("图片", "截图"),
    ".webp": ("图片", "截图"),
    ".svg": ("图片", "其他"),
    ".ico": ("图片", "其他"),
    ".psd": ("图片", "设计"),
    ".ai": ("图片", "设计"),
    ".sketch": ("图片", "设计"),
    # 音视频
    ".mp3": ("音视频", "音频"),
    ".wav": ("音视频", "音频"),
    ".flac": ("音视频", "音频"),
    ".aac": ("音视频", "音频"),
    ".ogg": ("音视频", "音频"),
    ".m4a": ("音视频", "音频"),
    ".wma": ("音视频", "音频"),
    ".mp4": ("音视频", "视频"),
    ".avi": ("音视频", "视频"),
    ".mkv": ("音视频", "视频"),
    ".mov": ("音视频", "视频"),
    ".wmv": ("音视频", "视频"),
    ".webm": ("音视频", "视频"),
    ".m4v": ("音视频", "视频"),
    # 压缩包
    ".zip": ("压缩包", ""),
    ".rar": ("压缩包", ""),
    ".7z": ("压缩包", ""),
    ".tar": ("压缩包", ""),
    ".gz": ("压缩包", ""),
    ".bz2": ("压缩包", ""),
    ".xz": ("压缩包", ""),
}

# ── 域名 → 网址子类 ──────────────────────────────

DOMAIN_CATEGORY = {
    "github.com": ("网址", "技术"),
    "gitlab.com": ("网址", "技术"),
    "gitee.com": ("网址", "技术"),
    "stackoverflow.com": ("网址", "技术"),
    "docs.python.org": ("网址", "技术"),
    "developer.mozilla.org": ("网址", "技术"),
    "w3.org": ("网址", "技术"),
    "arxiv.org": ("网址", "AI研究"),
    "paperswithcode.com": ("网址", "AI研究"),
    "huggingface.co": ("网址", "AI研究"),
    "openai.com": ("网址", "AI研究"),
    "anthropic.com": ("网址", "AI研究"),
    "news.ycombinator.com": ("网址", "新闻"),
    "infoq.cn": ("网址", "新闻"),
    "36kr.com": ("网址", "新闻"),
    "ithome.com": ("网址", "新闻"),
    "sspai.com": ("网址", "新闻"),
    "reddit.com": ("网址", "社交"),
    "twitter.com": ("网址", "社交"),
    "x.com": ("网址", "社交"),
    "weibo.com": ("网址", "社交"),
    "zhihu.com": ("网址", "社交"),
    "juejin.cn": ("网址", "社交"),
    "v2ex.com": ("网址", "社交"),
    "douban.com": ("网址", "社交"),
    "youtube.com": ("网址", "视频"),
    "bilibili.com": ("网址", "视频"),
    "vimeo.com": ("网址", "视频"),
    "medium.com": ("网址", "阅读"),
    "wikipedia.org": ("网址", "百科"),
    "baike.baidu.com": ("网址", "百科"),
}

# ── 关键词 → 标签 ────────────────────────────────

KEYWORD_TAGS = [
    # Python
    (r'\bpython\b', "Python"), (r'\bdjango\b', "Python"), (r'\bflask\b', "Python"),
    (r'\bfastapi\b', "Python"), (r'\bpytorch\b', "Python"), (r'\btensorflow\b', "Python"),
    (r'\bnumpy\b', "Python"), (r'\bpandas\b', "Python"), (r'\bscikit-learn\b', "Python"),
    (r'\bjupyter\b', "Python"), (r'\bconda\b', "Python"), (r'\bpip\b', "Python"),
    # 前端
    (r'\bjavascript\b', "前端"), (r'\btypescript\b', "前端"), (r'\breact\b', "前端"),
    (r'\bvue\b', "前端"), (r'\bangular\b', "前端"), (r'\bnext\.?js\b', "前端"),
    (r'\bnuxt\b', "前端"), (r'\bwebpack\b', "前端"), (r'\bvite\b', "前端"),
    (r'\bnode\.?js\b', "前端"), (r'\bnpm\b', "前端"),
    # DevOps
    (r'\bdocker\b', "DevOps"), (r'\bkubernetes\b', "DevOps"), (r'\bk8s\b', "DevOps"),
    (r'\bjenkins\b', "DevOps"), (r'\bci/cd\b', "DevOps"), (r'\bgithub\s+actions?\b', "DevOps"),
    (r'\bterraform\b', "DevOps"), (r'\bansible\b', "DevOps"), (r'\bdevops\b', "DevOps"),
    # AI/LLM
    (r'\bllm\b', "AI/LLM"), (r'\bgpt\b', "AI/LLM"), (r'\btransformer\b', "AI/LLM"),
    (r'\brag\b', "AI/LLM"), (r'\blangchain\b', "AI/LLM"), (r'\bembedding\b', "AI/LLM"),
    (r'\bfine.?tuning\b', "AI/LLM"), (r'\bprompt\b', "AI/LLM"), (r'\bagent\b', "AI/LLM"),
    (r'\bopenai\b', "AI/LLM"), (r'\banthropic\b', "AI/LLM"), (r'\bclaude\b', "AI/LLM"),
    (r'\bdeepseek\b', "AI/LLM"), (r'\bqwen\b', "AI/LLM"),
    # 数据库
    (r'\bsql\b', "数据库"), (r'\bmysql\b', "数据库"), (r'\bpostgresql\b', "数据库"),
    (r'\bpostgres\b', "数据库"), (r'\bmongodb\b', "数据库"), (r'\bredis\b', "数据库"),
    (r'\belasticsearch\b', "数据库"), (r'\bsqlite\b', "数据库"),
    # Linux/运维
    (r'\blinux\b', "Linux"), (r'\bbash\b', "Linux"), (r'\bnginx\b', "Linux"),
    (r'\bssh\b', "Linux"), (r'\bubuntu\b', "Linux"), (r'\bcentos\b', "Linux"),
    (r'\bsystemd\b', "Linux"), (r'\bapache\b', "运维"),
    # 其他
    (r'\bgit\b', "Git"), (r'\bapi\b', "API"), (r'\brest\b', "API"),
    (r'\bgraphql\b', "API"), (r'\bmicroservices?\b', "微服务"),
    (r'\bsecurity\b', "安全"), (r'\b加密\b', "安全"), (r'\bauth\b', "认证"),
]

# 预编译正则
KEYWORD_PATTERNS = [(re.compile(pattern, re.IGNORECASE), tag) for pattern, tag in KEYWORD_TAGS]


class ContentClassifier:
    """内容分类引擎"""

    # ── 主入口 ────────────────────────────────────

    def classify(self, file_info: FileInfo, source_url: str = "") -> tuple[str, list[str]]:
        """
        对已识别的文件信息进行分类。
        返回 (category_path, tags_list)
        category_path 格式如 "文档/代码"、"网址/技术"
        """
        category_path = "其他"
        tags: list[str] = []
        file_path = file_info.file_path
        ext = Path(file_path).suffix.lower() if file_path else ""

        # ── URL 分类 ──────────────────────────────
        if source_url or file_info.content_type == "url":
            url = source_url or file_info.metadata.get("url", "")
            if url:
                cat, sub = self._classify_url(url)
                category_path = f"{cat}/{sub}" if sub else cat
                tags = self._extract_keywords_from_text(
                    file_info.metadata.get("url_title", "") + " " + file_info.text_preview
                )
                return category_path, tags

        # ── 扩展名分类 ─────────────────────────────
        if ext in EXTENSION_CATEGORY:
            cat, sub = EXTENSION_CATEGORY[ext]
            category_path = f"{cat}/{sub}" if sub else cat

        # ── 截图 OCR 分类 ──────────────────────────
        elif file_info.content_type == "image" and file_info.text_preview:
            # OCR 文字 → 按关键词分类
            cat, sub = self._classify_by_keywords(file_info.text_preview)
            if cat:
                category_path = f"图片/{sub}" if sub else "图片/截图"
            else:
                category_path = "图片/截图"

        # ── 关键词标签 ─────────────────────────────
        text_for_tags = file_info.text_preview + " " + file_info.file_name
        tags = self._extract_keywords_from_text(text_for_tags)

        return category_path, tags

    # ── URL 分类 ──────────────────────────────────

    def classify_url(self, url: str, title: str = "") -> tuple[str, list[str]]:
        """独立 URL 分类入口"""
        cat, sub = self._classify_url(url)
        category_path = f"{cat}/{sub}" if sub else cat
        tags = self._extract_keywords_from_text(title + " " + url)
        return category_path, tags

    def _classify_url(self, url: str) -> tuple[str, str]:
        """URL → (大类, 子类)"""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
            # 去掉 www. 前缀
            if hostname.startswith("www."):
                hostname = hostname[4:]

            # 精确匹配
            if hostname in DOMAIN_CATEGORY:
                return DOMAIN_CATEGORY[hostname]

            # 后缀匹配（如 docs.python.org → 技术）
            for domain, (cat, sub) in DOMAIN_CATEGORY.items():
                if hostname.endswith("." + domain):
                    return (cat, sub)

            # TLD 推断
            if hostname.endswith(".github.io"):
                return ("网址", "技术")
            if hostname.endswith(".dev"):
                return ("网址", "技术")

        except Exception:
            pass

        return ("网址", "其他")

    # ── 关键词匹配 ────────────────────────────────

    def _classify_by_keywords(self, text: str) -> tuple[str, str]:
        """根据文本内容推断分类（用于截图 OCR）"""
        if not text:
            return ("", "")

        # 检查常见领域关键词
        tech_score = sum(1 for p, _ in KEYWORD_PATTERNS if p.search(text) and _ in ("Python", "前端", "DevOps", "AI/LLM", "数据库", "Linux", "Git", "API"))
        if tech_score >= 2:
            return ("图片", "技术截图")

        # 检查是否像聊天/社交内容
        chat_indicators = ["消息", "聊天", "对话", "群聊", "@", "回复"]
        if any(w in text for w in chat_indicators):
            return ("图片", "聊天截图")

        return ("图片", "截图")

    def _extract_keywords_from_text(self, text: str) -> list[str]:
        """从文本中提取关键词标签（去重）"""
        if not text:
            return []

        tags: list[str] = []
        seen: set[str] = set()

        for pattern, tag in KEYWORD_PATTERNS:
            if tag not in seen and pattern.search(text):
                tags.append(tag)
                seen.add(tag)

        return tags

    # ── LLM 分类接口（预留）────────────────────────

    def classify_by_llm(self, file_info: FileInfo, source_url: str = "") -> tuple[str, list[str]]:
        """
        预留的 LLM 分类接口。
        当前实现：回退到规则分类。
        后期接入：调用 LLM API，传入 text_preview，让模型返回分类和标签。
        """
        # TODO: 接入 LLM API
        # prompt = f"请对以下内容分类：\n标题：{file_info.title}\n内容摘要：{file_info.text_preview[:500]}\n\n返回 JSON: {"category_path": "xx/xx", "tags": ["tag1", "tag2"]}"
        # result = llm_api.chat(prompt)
        # return result["category_path"], result["tags"]
        return self.classify(file_info, source_url)

    # ── 分类规则从数据库加载（可选增强）─────────────

    def load_from_db(self, db) -> None:
        """从 SQLite classification_rules 表加载追加规则"""
        try:
            rows = db.execute(
                "SELECT rule_type, category, subcategory, pattern FROM classification_rules WHERE enabled=1 ORDER BY priority DESC"
            ).fetchall()
            for row in rows:
                rule_type = row["rule_type"]
                category = row["category"]
                subcategory = row["subcategory"]
                pattern = row["pattern"]
                if rule_type == "domain":
                    DOMAIN_CATEGORY[pattern] = (category, subcategory)
                elif rule_type == "keyword":
                    KEYWORD_PATTERNS.append((re.compile(re.escape(pattern), re.IGNORECASE), category))
            logger.info(f"从数据库加载分类规则: {len(rows)} 条")
        except Exception as e:
            logger.warning(f"加载数据库分类规则失败: {e}")
