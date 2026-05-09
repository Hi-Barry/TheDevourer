"""大嘴怪 — 存储与检索引擎

StorageManager：文件入库、MD5 去重、FTS5 + ChromaDB 双引擎混合搜索。
"""
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime

from core.config import get_config
from core.db import Database
from core.chroma_client import ChromaClient, init_chroma
from core.file_classifier import FileClassifier, FileInfo
from core.content_classifier import ContentClassifier
from core.logger import get_logger

logger = get_logger()


class StorageManager:
    """文件存储管理器，负责入库、去重、搜索"""

    def __init__(self, db: Database, chroma: ChromaClient = None):
        self.db = db
        self.chroma = chroma
        self.config = get_config()
        self.classifier = FileClassifier()
        self.categorizer = ContentClassifier()

    # ── 入库 ──────────────────────────────────────

    def ingest_file(self, file_path: str, source_url: str = "",
                    source_app: str = "") -> Optional[str]:
        """
        将文件入库。
        返回 item_id，重复时返回 None。
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"入库失败：文件不存在 {file_path}")
            return None

        # 1. 识别文件
        file_info = self.classifier.identify(file_path)
        if file_info.error:
            logger.warning(f"入库失败：无法识别 {file_path} — {file_info.error}")
            return None

        # 2. MD5 去重
        existing = self.db.get_item_by_checksum(file_info.checksum)
        if existing:
            logger.info(f"去重：文件已存在 {file_path} (existing: {existing['id']})")
            return None

        # 3. 分类
        category_path, tags = self.categorizer.classify(file_info, source_url)

        # 4. 生成存储路径
        item_id = str(uuid.uuid4())
        repo_path = self._build_repo_path(category_path, item_id, path.name)

        # 5. 复制文件到仓库
        self._copy_to_repo(path, repo_path)

        # 6. 写入 SQLite
        item_dict = {
            "id": item_id,
            "type": file_info.content_type,
            "title": file_info.title or path.stem,
            "source_path": str(path),
            "source_url": source_url,
            "repo_path": repo_path,
            "category": category_path,
            "tags": self._tags_to_json(tags),
            "file_size": file_info.file_size,
            "checksum": file_info.checksum,
            "mime_type": file_info.mime_type,
            "metadata_json": file_info.metadata if isinstance(file_info.metadata, str)
                           else __import__("json").dumps(file_info.metadata, ensure_ascii=False),
            "text_content": file_info.text_preview,
            "text_length": file_info.text_length,
            "embedding_status": "pending",
            "source_app": source_app,
        }
        self.db.insert_item(item_dict)

        logger.info(f"入库成功: {item_id[:8]} | {category_path} | {path.name}")
        return item_id

    def ingest_url(self, url: str, title: str = "", source_app: str = "") -> str:
        """将 URL 入库为虚拟内容项"""
        item_id = str(uuid.uuid4())
        category_path, tags = self.categorizer.classify_url(url, title)

        # URL 在仓库中以 .url 文件形式存储
        url_file_name = f"{item_id[:8]}_{(title or url[:30]).replace('/', '_')}.url"
        repo_path = self._build_repo_path(category_path, item_id, url_file_name)

        # 写入 .url 文件
        repo_full = Path(self.config.files_path) / repo_path
        repo_full.parent.mkdir(parents=True, exist_ok=True)
        with open(repo_full, "w", encoding="utf-8") as f:
            f.write(f"[InternetShortcut]\nURL={url}\n")

        text_content = f"URL: {url}\nTitle: {title}"

        item_dict = {
            "id": item_id,
            "type": "url",
            "title": title or url[:100],
            "source_url": url,
            "repo_path": repo_path,
            "category": category_path,
            "tags": self._tags_to_json(tags),
            "file_size": len(text_content),
            "checksum": "",
            "mime_type": "text/url",
            "metadata_json": '{"url": "' + url + '", "title": "' + (title or "").replace('"', '\\"') + '"}',
            "text_content": text_content,
            "text_length": len(text_content),
            "embedding_status": "pending",
            "source_app": source_app,
        }
        self.db.insert_item(item_dict)
        logger.info(f"URL入库: {item_id[:8]} | {category_path} | {title}")
        return item_id

    def ingest_text(self, text: str, source_app: str = "") -> str:
        """将纯文本入库"""
        item_id = str(uuid.uuid4())
        # 文件名用文本前30字
        safe_name = text[:30].replace("\n", " ").replace("/", "_").strip() or "note"
        txt_file_name = f"{item_id[:8]}_{safe_name}.txt"
        repo_path = self._build_repo_path("文档/笔记", item_id, txt_file_name)

        # 写入 txt
        repo_full = Path(self.config.files_path) / repo_path
        repo_full.parent.mkdir(parents=True, exist_ok=True)
        repo_full.write_text(text, encoding="utf-8")

        tags = self.categorizer._extract_keywords_from_text(text)

        item_dict = {
            "id": item_id,
            "type": "document",
            "title": safe_name,
            "repo_path": repo_path,
            "category": "文档/笔记",
            "tags": self._tags_to_json(tags),
            "file_size": len(text.encode("utf-8")),
            "checksum": "",
            "mime_type": "text/plain",
            "metadata_json": "{}",
            "text_content": text,
            "text_length": len(text),
            "embedding_status": "pending",
            "source_app": source_app,
        }
        self.db.insert_item(item_dict)
        logger.info(f"文本入库: {item_id[:8]} | 文档/笔记 | {len(text)}字")
        return item_id

    # ── 文件操作 ──────────────────────────────────

    def _build_repo_path(self, category_path: str, item_id: str,
                         original_name: str) -> str:
        """构建仓库内相对路径"""
        # 安全化文件名，避免特殊字符
        safe_name = original_name.replace("\\", "_").replace("/", "_")
        # 限制文件名长度
        if len(safe_name) > 120:
            name_part = safe_name[:80]
            ext = Path(safe_name).suffix
            safe_name = name_part + "..." + ext

        return f"{category_path}/{item_id[:8]}_{safe_name}"

    def _copy_to_repo(self, src: Path, repo_rel_path: str) -> None:
        """将文件复制到仓库目录"""
        dest = Path(self.config.files_path) / repo_rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        # 尝试硬链接，失败则复制
        try:
            os.link(str(src), str(dest))
        except (OSError, NotImplementedError):
            shutil.copy2(str(src), str(dest))

    # ── 搜索 ──────────────────────────────────────

    def search_fts(self, query: str, limit: int = 20) -> list[dict]:
        """FTS5 关键词搜索"""
        return self.db.search_fts(query, limit)

    def search_vector(self, query: str, top_k: int = 10) -> list[dict]:
        """ChromaDB 语义搜索"""
        if not self.chroma or self.chroma.count() == 0:
            return []
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(self.config.embedding_model)
            embedding = model.encode([query])[0].tolist()
            return self.chroma.search(embedding, top_k)
        except ImportError:
            logger.warning("sentence-transformers 不可用，语义搜索降级")
            return []
        except Exception as e:
            logger.warning(f"语义搜索失败: {e}")
            return []

    def search_hybrid(self, query: str, limit: int = 10) -> list[dict]:
        """
        混合搜索：FTS5 + 语义搜索 → 去重合并排序。
        返回统一格式的搜索结果列表。
        """
        results: dict[str, dict] = {}  # key: item_id

        # FTS5 搜索
        fts_results = self.search_fts(query, limit * 2)
        for r in fts_results:
            item_id = r["id"]
            results[item_id] = {
                "item_id": item_id,
                "title": r["title"],
                "category": r["category"],
                "tags": r.get("tags", "[]"),
                "repo_path": r.get("repo_path", ""),
                "type": r["type"],
                "snippet": (r.get("text_content", "") or "")[:300],
                "score": 1.0,  # FTS5 默认分数
                "source": "fts",
            }

        # ChromaDB 语义搜索
        vector_results = self.search_vector(query, limit)
        for vr in vector_results:
            meta = vr.get("metadata", {})
            item_id = meta.get("item_id", vr.get("id", ""))
            distance = vr.get("distance", 1.0)
            # 余弦距离 → 相似度分数 (ChromaDB 默认用余弦距离)
            similarity = 1.0 - min(distance, 2.0) / 2.0

            if item_id in results:
                # 已存在，取高分
                results[item_id]["score"] = max(results[item_id]["score"], similarity)
                results[item_id]["source"] = "hybrid"
            else:
                # 新条目：从 SQLite 补充完整信息
                item = self.db.get_item(item_id)
                if item:
                    results[item_id] = {
                        "item_id": item_id,
                        "title": item["title"],
                        "category": item["category"],
                        "tags": item.get("tags", "[]"),
                        "repo_path": item.get("repo_path", ""),
                        "type": item["type"],
                        "snippet": vr.get("document", "")[:300],
                        "score": similarity,
                        "source": "vector",
                    }
                else:
                    # ChromaDB 中有但 SQLite 已被删除，跳过
                    pass

        # 按分数降序排序，取前 limit
        sorted_results = sorted(
            results.values(), key=lambda x: x["score"], reverse=True
        )[:limit]

        return sorted_results

    # ── 索引管理 ──────────────────────────────────

    def index_item(self, item_id: str) -> bool:
        """对单个内容项生成向量并写入 ChromaDB"""
        if not self.chroma:
            return False

        item = self.db.get_item(item_id)
        if not item:
            return False

        text = item.get("text_content", "")
        if not text or len(text.strip()) < 10:
            self.db.update_embedding_status(item_id, "skipped")
            return False

        try:
            # 更新状态
            self.db.update_embedding_status(item_id, "indexing")

            # 文本分块
            chunks = self._chunk_text(text)

            # 构建元数据
            metadata = {
                "title": item["title"],
                "category": item["category"],
                "tags": item.get("tags", "[]"),
                "file_path": item.get("repo_path", ""),
                "type": item["type"],
            }

            # 写入 ChromaDB
            self.chroma.add_chunks(item_id, chunks, metadata)
            self.db.update_embedding_status(item_id, "done")
            logger.debug(f"索引完成: {item_id[:8]} ({len(chunks)} chunks)")
            return True

        except Exception as e:
            self.db.update_embedding_status(item_id, "failed")
            logger.warning(f"索引失败: {item_id[:8]} — {e}")
            return False

    def index_pending(self, limit: int = 50) -> int:
        """批量索引 pending 项，返回已索引数量"""
        items = self.db.get_pending_embeddings(limit)
        count = 0
        for item in items:
            if self.index_item(item["id"]):
                count += 1
        if count:
            logger.info(f"批量索引: {count}/{len(items)} 完成")
        return count

    def _chunk_text(self, text: str, chunk_size: int = 500,
                    overlap: int = 50) -> list[str]:
        """简单文本分块"""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap
        return chunks

    # ── 删除 ──────────────────────────────────────

    def delete_item(self, item_id: str) -> bool:
        """删除内容和相关文件"""
        item = self.db.get_item(item_id)
        if not item:
            return False

        # 删除仓库中的文件
        repo_full = Path(self.config.files_path) / item.get("repo_path", "")
        if repo_full.exists():
            repo_full.unlink(missing_ok=True)

        # 删除 ChromaDB 索引
        if self.chroma:
            self.chroma.delete_item(item_id)

        # 删除 SQLite 记录
        self.db.execute("DELETE FROM content_items WHERE id=?", (item_id,))
        self.db.commit()
        logger.info(f"已删除: {item_id[:8]} | {item.get('title', '')}")
        return True

    # ── 导出 ──────────────────────────────────────

    def export_items(self, item_ids: list[str], output_dir: str) -> str:
        """导出指定内容项到目录"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        count = 0
        for item_id in item_ids:
            item = self.db.get_item(item_id)
            if not item:
                continue
            repo_full = Path(self.config.files_path) / item.get("repo_path", "")
            if repo_full.exists():
                dest = Path(output_dir) / repo_full.name
                shutil.copy2(str(repo_full), str(dest))
                count += 1

        logger.info(f"导出 {count}/{len(item_ids)} 项到 {output_dir}")
        return output_dir

    def export_by_category(self, category: str, output_dir: str) -> str:
        """按分类导出"""
        items = self.db.list_items(category=category, limit=10000)
        ids = [i["id"] for i in items]
        return self.export_items(ids, output_dir)

    # ── 工具 ──────────────────────────────────────

    @staticmethod
    def _tags_to_json(tags: list[str]) -> str:
        import json
        return json.dumps(tags, ensure_ascii=False)
