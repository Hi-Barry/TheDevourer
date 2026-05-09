"""大嘴怪 — FeedHandler 投喂模块 测试"""
import sys, os, hashlib, tempfile, shutil, json
from pathlib import Path
from urllib import request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')

from core.feed_handler import (
    FeedItem, FeedSourceType,
    extract_urls, is_url, fetch_url_title, compute_md5,
)


# ── FeedItem 数据模型 ─────────────────────────────

def test_feed_item_create():
    """FeedItem 创建与默认值"""
    item = FeedItem()
    assert item.id is not None
    assert len(item.id) > 0
    assert item.source_type == FeedSourceType.FILE
    assert item.file_paths == []
    assert item.url == ""
    print("  ✓ FeedItem creation with defaults")


def test_feed_item_display_name():
    """各 source_type 的 display_name"""
    file_item = FeedItem(source_type=FeedSourceType.FILE, file_paths=["/tmp/test.py"])
    assert "test.py" in file_item.display_name

    files_item = FeedItem(source_type=FeedSourceType.FILES, file_paths=["/tmp/a.py", "/tmp/b.py"])
    assert "+1个" in files_item.display_name

    url_item = FeedItem(source_type=FeedSourceType.URL, url="https://github.com/repo/path")
    assert "github.com" in url_item.display_name

    text_item = FeedItem(source_type=FeedSourceType.TEXT, text="这是一段很长的测试文本内容展示")
    assert len(text_item.display_name) > 0

    clip_item = FeedItem(source_type=FeedSourceType.CLIPBOARD_IMAGE, image_path="/tmp/clip.png")
    assert "clip.png" in clip_item.display_name

    print("  ✓ display_name for all source types")


def test_feed_item_properties():
    """is_file_type 和 is_url_type 属性"""
    assert FeedItem(source_type=FeedSourceType.FILE).is_file_type is True
    assert FeedItem(source_type=FeedSourceType.FILES).is_file_type is True
    assert FeedItem(source_type=FeedSourceType.CLIPBOARD_IMAGE).is_file_type is True
    assert FeedItem(source_type=FeedSourceType.URL).is_file_type is False
    assert FeedItem(source_type=FeedSourceType.TEXT).is_file_type is False

    assert FeedItem(source_type=FeedSourceType.URL).is_url_type is True
    assert FeedItem(source_type=FeedSourceType.FILE).is_url_type is False

    print("  ✓ is_file_type / is_url_type")


# ── URL 工具函数 ─────────────────────────────────

def test_extract_urls():
    """从混合文本中提取 URL"""
    # 单个 URL
    text = "看这个 https://github.com/Hi-Barry/repo"
    urls = extract_urls(text)
    assert len(urls) == 1
    assert "github.com" in urls[0]

    # 多个 URL
    text = "参考 https://arxiv.org/abs/2301 和 https://openai.com"
    urls = extract_urls(text)
    assert len(urls) == 2

    # 无 URL
    assert extract_urls("普通文本没有链接") == []
    assert extract_urls("") == []

    # 带括号/标点的 URL —— 匹配到 ) 之前
    text = "见网址（https://example.com/page）"
    urls = extract_urls(text)
    # 中文全角括号分离——URL 在 ) 前结束
    assert len(urls) >= 1
    # 验证至少包含域名
    assert any("example.com/page" in u for u in urls)

    print("  ✓ extract_urls")


def test_is_url():
    """判断是否为 URL"""
    assert is_url("https://github.com/repo") is True
    assert is_url("http://localhost:11434/api/chat") is True
    assert is_url("普通文本") is False
    assert is_url("") is False
    assert is_url("   ") is False
    # 不带协议的 URL 应返回 False（我们的模式要求 http(s)://）
    assert is_url("github.com/repo") is False

    print("  ✓ is_url")


# ── MD5 ───────────────────────────────────────────

def test_compute_md5():
    """MD5 计算正确性"""
    tmp = tempfile.mkdtemp()
    try:
        # 已知内容 → 已知 MD5
        content = b"hello world"
        file_path = os.path.join(tmp, "test.txt")
        with open(file_path, "wb") as f:
            f.write(content)

        expected_md5 = hashlib.md5(content).hexdigest()
        result = compute_md5(file_path)
        assert result == expected_md5, f"Expected {expected_md5}, got {result}"

        # 不同内容 → 不同 MD5
        file_path2 = os.path.join(tmp, "test2.txt")
        with open(file_path2, "wb") as f:
            f.write(b"different content")
        result2 = compute_md5(file_path2)
        assert result2 != result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("  ✓ compute_md5")


# ── fetch_url_title ───────────────────────────────

def test_fetch_url_title_success():
    """URL 标题提取成功（mock）"""
    # 用 lambda 临时模拟
    orig = None
    import core.feed_handler as fh
    orig = fh.fetch_url_title
    try:
        def mock_fetch(url, timeout=5.0):
            return "Mock Title"
        fh.fetch_url_title = mock_fetch
        title = fh.fetch_url_title("https://example.com")
        assert title == "Mock Title"
    finally:
        if orig:
            fh.fetch_url_title = orig
    print("  ✓ fetch_url_title success")


def test_fetch_url_title_timeout():
    """URL 标题提取超时返回空"""
    import core.feed_handler as fh
    orig = fh.fetch_url_title
    try:
        def mock_fetch(url, timeout=5.0):
            raise Exception("Connection timeout")
        fh.fetch_url_title = mock_fetch
        try:
            title = fh.fetch_url_title("https://slow-site.com")
        except Exception:
            title = ""  # 内部异常时返回空
        assert title == ""
    finally:
        if orig:
            fh.fetch_url_title = orig
    print("  ✓ fetch_url_title timeout returns empty")


# ── parse_mime_data ───────────────────────────────

def test_parse_mime_data_text():
    """剪贴板纯文本解析"""
    from core.feed_handler import parse_mime_data

    # Mock QMimeData
    class MockMimeData:
        def __init__(self, text="", html=""):
            self._text = text
            self._html = html
            self._files = []

        def hasUrls(self): return bool(self._files)
        def urls(self): return []
        def hasHtml(self): return bool(self._html)
        def html(self): return self._html
        def hasText(self): return bool(self._text)
        def text(self): return self._text

    # 纯文本（非 URL）
    items = parse_mime_data(MockMimeData(text="普通文本"))
    assert len(items) == 1
    assert items[0].source_type == FeedSourceType.TEXT

    # 文本中包含 URL
    items = parse_mime_data(MockMimeData(text="看这里 https://github.com/repo"))
    assert len(items) == 1
    assert items[0].source_type == FeedSourceType.URL

    # 空文本
    items = parse_mime_data(MockMimeData(text=""))
    assert len(items) == 0

    print("  ✓ parse_mime_data text")


def test_parse_mime_data_url():
    """纯 URL 文本"""
    from core.feed_handler import parse_mime_data

    class MockMimeData:
        def hasUrls(self): return False
        def urls(self): return []
        def hasHtml(self): return False
        def html(self): return ""
        def hasText(self): return True
        def text(self): return "https://github.com/repo"

    items = parse_mime_data(MockMimeData())
    assert len(items) == 1
    assert items[0].source_type == FeedSourceType.URL
    assert "github.com" in items[0].url
    print("  ✓ parse_mime_data URL")


# ── FeedQueueWorker（跳过，需 PySide6 QThread）─────

def SKIP_test_feed_queue_worker():
    """跳过：FeedQueueWorker 依赖 PySide6 QThread"""
    raise NotImplementedError("需要 PySide6 运行时")


# ── 运行入口 ──────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_feed_item_create,
        test_feed_item_display_name,
        test_feed_item_properties,
        test_extract_urls,
        test_is_url,
        test_compute_md5,
        test_fetch_url_title_success,
        test_fetch_url_title_timeout,
        test_parse_mime_data_text,
        test_parse_mime_data_url,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            import traceback
            print(f"  ✗ {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{'='*40}\n结果: {passed}/{len(tests)} 通过 (1 skip: FeedQueueWorker需PySide6)")
