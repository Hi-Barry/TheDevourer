"""大嘴怪 — 投喂处理模块

投喂数据模型 + 投喂队列工作线程。
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import uuid
import hashlib
import re

# PySide6 延迟导入（测试可 mock）
try:
    from PySide6.QtCore import QThread, Signal, QMimeData, QUrl
    _HAS_QT = True
except ImportError:
    # 创建 mock Signal 类——模拟 PySide6 的 Signal 描述符
    class Signal:
        """Mock PySide6 Signal，允许 class 属性定义"""
        def __init__(self, *types):
            self._types = types
        def __get__(self, obj, objtype=None):
            return self
        def connect(self, slot): pass
        def emit(self, *args): pass
        def __call__(self, *args):
            return self

    from unittest.mock import MagicMock
    QThread = type("QThread", (object,), {
        "msleep": staticmethod(lambda ms: None),
        "wait": lambda self, ms: True,
    })
    QMimeData = type("QMimeData", (object,), {
        "hasUrls": lambda self: False,
        "urls": lambda self: [],
        "hasHtml": lambda self: False,
        "html": lambda self: "",
        "hasText": lambda self: False,
        "text": lambda self: "",
    })
    QUrl = type("QUrl", (object,), {
        "isLocalFile": lambda self: False,
        "toLocalFile": lambda self: "",
        "toString": lambda self: "",
    })
    _HAS_QT = False


# ── 投喂项数据模型 ────────────────────────────────

class FeedSourceType:
    FILE = "file"
    FILES = "files"           # 多文件
    URL = "url"
    TEXT = "text"
    CLIPBOARD_IMAGE = "clipboard_image"


@dataclass
class FeedItem:
    """单次投喂的数据载体"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_type: str = FeedSourceType.FILE        # file/files/url/text/clipboard_image
    file_paths: list[str] = field(default_factory=list)
    url: str = ""
    url_title: str = ""                              # URL 标题（拖入时为空，后续异步填充）
    text: str = ""                                   # 纯文本投喂
    image_path: str = ""                             # 剪贴板图片保存路径

    @property
    def display_name(self) -> str:
        """用于气泡显示的简短名称"""
        if self.source_type == FeedSourceType.URL:
            return self.url[:60] + ("..." if len(self.url) > 60 else "")
        if self.file_paths:
            name = Path(self.file_paths[0]).name
            n = len(self.file_paths)
            return f"{name} (+{n - 1}个)" if n > 1 else name
        if self.text:
            return self.text[:30] + ("..." if len(self.text) > 30 else "")
        if self.image_path:
            return f"📷 {Path(self.image_path).name}"
        return "未知内容"

    @property
    def is_file_type(self) -> bool:
        return self.source_type in (FeedSourceType.FILE, FeedSourceType.FILES, FeedSourceType.CLIPBOARD_IMAGE)

    @property
    def is_url_type(self) -> bool:
        return self.source_type == FeedSourceType.URL


# ── 工具函数 ───────────────────────────────────

_URL_PATTERN = re.compile(
    r'https?://[^\s<>"\'{}|\\^`\[\]]+',
    re.IGNORECASE
)

_URL_TITLE_PATTERN = re.compile(r'<title[^>]*>(.*?)</title>', re.IGNORECASE | re.DOTALL)


def extract_urls(text: str) -> list[str]:
    """从文本中提取所有 URL"""
    return _URL_PATTERN.findall(text)


def is_url(text: str) -> bool:
    """判断文本是否为单个 URL"""
    text = text.strip()
    return bool(_URL_PATTERN.fullmatch(text))


def fetch_url_title(url: str, timeout: float = 5.0) -> str:
    """尝试获取网页标题，失败返回空"""
    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                return ""
            html = resp.read(4096 * 4).decode("utf-8", errors="ignore")  # 只读前 16KB
            match = _URL_TITLE_PATTERN.search(html)
            if match:
                title = match.group(1).strip()
                # 清理 HTML 实体
                title = title.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
                return title[:200]  # 截断过长标题
    except Exception:
        pass
    return ""


def compute_md5(file_path: str) -> str:
    """计算文件 MD5"""
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── 投喂队列线程 ──────────────────────────────────

class FeedQueueWorker(QThread):
    """后台线程，逐项处理投喂队列"""

    # item_started(item: FeedItem)
    item_started = Signal(object)
    # item_finished(item: FeedItem, success: bool, message: str)
    item_finished = Signal(object, bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: list[FeedItem] = []
        self._running = False

    def enqueue(self, item: FeedItem) -> None:
        """加入投喂队列"""
        self._queue.append(item)
        if not self._running:
            self.start()

    def enqueue_items(self, items: list[FeedItem]) -> None:
        """批量加入"""
        self._queue.extend(items)
        if not self._running:
            self.start()

    def run(self) -> None:
        """线程主循环：逐项处理队列"""
        self._running = True
        while self._queue and self._running:
            item = self._queue.pop(0)
            self.item_started.emit(item)

            # ── 现阶段：占位处理，后续集成 FileClassifier + StorageManager ──
            try:
                if item.is_file_type:
                    for fp in item.file_paths or []:
                        if not Path(fp).exists():
                            raise FileNotFoundError(f"文件不存在: {fp}")
                    self.msleep(200)  # 模拟处理
                    result_msg = f"已收到 {item.display_name}"
                    self.item_finished.emit(item, True, result_msg)

                elif item.is_url_type:
                    # 异步获取标题
                    title = fetch_url_title(item.url)
                    if title:
                        item.url_title = title
                    result_msg = f"已收到 URL: {title or item.url[:50]}"
                    self.item_finished.emit(item, True, result_msg)

                elif item.source_type == FeedSourceType.TEXT:
                    result_msg = f"已收到文本 ({len(item.text)} 字)"
                    self.item_finished.emit(item, True, result_msg)

                else:
                    result_msg = "已收到未知内容"
                    self.item_finished.emit(item, True, result_msg)

            except Exception as e:
                self.item_finished.emit(item, False, str(e))

        self._running = False

    def stop(self) -> None:
        self._running = False
        self.wait(2000)


# ── MIME 数据解析 ──────────────────────────────────

def parse_mime_data(mime: QMimeData) -> list[FeedItem]:
    """解析拖放/粘贴的 MIME 数据，返回 FeedItem 列表"""
    items: list[FeedItem] = []

    # 优先级 1: 文件列表
    if mime.hasUrls():
        urls = mime.urls()
        file_paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        web_urls = [u.toString() for u in urls if not u.isLocalFile()]

        # URL（非本地文件）
        for wurl in web_urls:
            items.append(FeedItem(
                source_type=FeedSourceType.URL,
                url=wurl,
            ))
        # 本地文件
        if file_paths:
            source_type = FeedSourceType.FILES if len(file_paths) > 1 else FeedSourceType.FILE
            items.append(FeedItem(
                source_type=source_type,
                file_paths=file_paths,
            ))
        return items

    # 优先级 2: HTML（可能含链接）
    if mime.hasHtml():
        html = mime.html()
        urls = extract_urls(html)
        if urls:
            items.append(FeedItem(
                source_type=FeedSourceType.URL,
                url=urls[0],
            ))
            return items

    # 优先级 3: 纯文本
    if mime.hasText():
        text = mime.text().strip()
        if text:
            # 判断是否为 URL
            if is_url(text):
                items.append(FeedItem(
                    source_type=FeedSourceType.URL,
                    url=text,
                ))
            else:
                # 提取文本中的 URL
                urls_in_text = extract_urls(text)
                if urls_in_text:
                    for u in urls_in_text:
                        items.append(FeedItem(
                            source_type=FeedSourceType.URL,
                            url=u,
                        ))
                else:
                    items.append(FeedItem(
                        source_type=FeedSourceType.TEXT,
                        text=text,
                    ))
        return items

    return items
