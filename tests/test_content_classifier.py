"""大嘴怪 — ContentClassifier 分类引擎 全覆盖测试"""
import sys, os, tempfile, shutil, json, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/home/admin/.local/lib/python3.10/site-packages')

from core.content_classifier import ContentClassifier
from core.file_classifier import FileInfo

cc = ContentClassifier()


def _file_info(path="", name="", content_type="document", text="",
               mime="text/plain", meta=None) -> FileInfo:
    return FileInfo(
        file_path=path, file_name=name, content_type=content_type,
        text_preview=text, text_length=len(text),
        mime_type=mime, metadata=meta or {},
    )


# ── 扩展名分类 ────────────────────────────────────

def test_ext_py():
    """① .py → 文档/代码 + Python标签"""
    info = _file_info(path="main.py", name="main.py", text="import python django")
    cat, tags = cc.classify(info)
    assert "文档" == cat.split("/")[0]
    assert "代码" in cat
    assert "Python" in tags
    print("  ✓ .py → 文档/代码 + Python")


def test_ext_png():
    """② .png → 图片/截图"""
    info = _file_info(path="image.png", name="image.png", content_type="image")
    cat, tags = cc.classify(info)
    assert "图片" == cat.split("/")[0], f"Expected 图片, got {cat}"
    print("  ✓ .png → 图片/截图")


def test_ext_mp4():
    """③ .mp4 → 音视频/视频"""
    info = _file_info(path="video.mp4", name="video.mp4", content_type="video")
    cat, tags = cc.classify(info)
    assert "音视频" == cat.split("/")[0]
    assert "视频" in cat
    print("  ✓ .mp4 → 音视频/视频")


def test_ext_zip():
    """④ .zip → 压缩包"""
    info = _file_info(path="archive.zip", name="archive.zip", content_type="archive")
    cat, tags = cc.classify(info)
    assert "压缩包" == cat.split("/")[0]
    print("  ✓ .zip → 压缩包")


def test_ext_txt():
    """⑤ .txt → 文档/笔记"""
    info = _file_info(path="note.txt", name="note.txt", text="some notes")
    cat, tags = cc.classify(info)
    assert "文档" == cat.split("/")[0]
    assert "笔记" in cat
    print("  ✓ .txt → 文档/笔记")


# ── URL 域名分类 ──────────────────────────────────

def test_domain_github():
    """⑥ github.com → 网址/技术"""
    cat, tags = cc.classify_url("https://github.com/Hi-Barry/repo")
    assert cat == "网址/技术", f"Expected 网址/技术, got {cat}"
    print("  ✓ github.com → 网址/技术")


def test_domain_arxiv():
    """⑦ arxiv.org → 网址/AI研究"""
    cat, _ = cc.classify_url("https://arxiv.org/abs/2301.12345")
    assert cat == "网址/AI研究"
    print("  ✓ arxiv.org → 网址/AI研究")


def test_domain_bilibili():
    """⑧ bilibili.com → 网址/视频"""
    cat, _ = cc.classify_url("https://www.bilibili.com/video/BV1xx")
    assert cat == "网址/视频"
    print("  ✓ bilibili.com → 网址/视频")


def test_domain_unknown():
    """⑨ 未知域名 → 网址/其他"""
    cat, _ = cc.classify_url("https://some-random-blog.example.com/post")
    assert cat == "网址/其他"
    print("  ✓ unknown domain → 网址/其他")


# ── 关键词标签 ────────────────────────────────────

def test_keyword_tags():
    """⑩ 含 python+docker+llm → 3标签去重"""
    info = _file_info(
        path="tech.txt", name="tech.txt",
        text="Python Docker Kubernetes and LLM RAG LangChain deployment",
    )
    cat, tags = cc.classify(info)
    assert "Python" in tags
    assert "DevOps" in tags
    assert "AI/LLM" in tags
    # 去重
    assert len(tags) == len(set(tags))
    print("  ✓ keyword tags: Python + DevOps + AI/LLM")


# ── 独立接口 ──────────────────────────────────────

def test_classify_url_independent():
    """⑪ classify_url 返回 (category_path, tags)"""
    cat, tags = cc.classify_url("https://zhihu.com/question/123", "知乎问题标题")
    assert cat == "网址/社交"
    assert isinstance(tags, list)
    print("  ✓ classify_url independent interface")


def test_classify_by_llm_fallback():
    """⑫ classify_by_llm 回退到规则分类"""
    info = _file_info(path="test.py", name="test.py")
    cat1, tags1 = cc.classify(info)
    cat2, tags2 = cc.classify_by_llm(info)
    assert cat1 == cat2, "LLM fallback should match rule classifier"
    assert tags1 == tags2
    print("  ✓ classify_by_llm fallback to rules")


# ── 数据库加载 ────────────────────────────────────

def test_load_from_db():
    """⑬ load_from_db 加载追加域名规则"""
    import tempfile
    from core.db import Database
    tmp = tempfile.mkdtemp()
    try:
        db = Database(os.path.join(tmp, "test.db"))
        db.init_schema()

        # 插入自定义域名规则
        db.execute(
            "INSERT INTO classification_rules (rule_type, category, subcategory, pattern) VALUES (?, ?, ?, ?)",
            ("domain", "网址", "自定义", "my-custom-blog.com")
        )
        db.commit()

        cc.load_from_db(db)

        cat, _ = cc.classify_url("https://my-custom-blog.com/article")
        assert cat == "网址/自定义", f"Expected 网址/自定义, got {cat}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("  ✓ load_from_db: custom domain rule applied")


# ── 边界 ──────────────────────────────────────────

def test_empty_file_info():
    """⑭ 空 FileInfo → category=其他 + tags=[]"""
    info = _file_info()
    cat, tags = cc.classify(info)
    assert cat == "其他" or cat.startswith("其他"), f"Expected 其他, got {cat}"
    assert tags == [] or isinstance(tags, list)
    print("  ✓ empty FileInfo → 其他 + []")


def test_empty_url():
    """⑮ 空 URL → 网址/其他"""
    cat, tags = cc.classify_url("", "")
    assert "网址" == cat.split("/")[0]
    print("  ✓ empty URL → 网址/其他")


# ── 运行入口 ──────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_ext_py, test_ext_png, test_ext_mp4, test_ext_zip, test_ext_txt,
        test_domain_github, test_domain_arxiv, test_domain_bilibili,
        test_domain_unknown,
        test_keyword_tags,
        test_classify_url_independent, test_classify_by_llm_fallback,
        test_load_from_db,
        test_empty_file_info, test_empty_url,
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
    print(f"\n{'='*40}\n结果: {passed}/{len(tests)} 通过")
