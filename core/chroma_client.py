"""大嘴怪 — ChromaDB 向量存储客户端

封装 ChromaDB 的连接、集合创建、增删查操作。
"""
from pathlib import Path
from typing import Optional

# chromadb 在 __init__ 中延迟导入（numpy 跨版本冲突）
from core.logger import get_logger

COLLECTION_NAME = "big_mouth_kb"


class ChromaClient:
    """ChromaDB 持久化客户端"""

    def __init__(self, persist_dir: str):
        self.persist_dir = str(persist_dir)
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
        # 延迟导入 chromadb（numpy 跨版本冲突）
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        self._client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = None
        self.logger = get_logger()

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"description": "大嘴怪知识库向量存储"},
            )
        return self._collection

    def get_or_create(self):
        """确保集合存在（幂等）"""
        return self.collection

    def add_chunks(self, item_id: str, chunks: list[str],
                   metadata: dict = None) -> None:
        """批量添加文本块及其向量"""
        if not chunks:
            return
        n = len(chunks)
        ids = [f"{item_id}_chunk_{i}" for i in range(n)]
        metas = []
        for i in range(n):
            meta = (metadata or {}).copy()
            meta["item_id"] = item_id
            meta["chunk_index"] = i
            meta["total_chunks"] = n
            metas.append(meta)

        self.collection.add(
            documents=chunks,
            ids=ids,
            metadatas=metas,
        )
        self.logger.debug(f"ChromaDB: 添加 {n} chunks (item={item_id})")

    def delete_item(self, item_id: str) -> None:
        """删除某个 item 的所有 chunk"""
        results = self.collection.get(
            where={"item_id": item_id},
            include=[],
        )
        if results and results["ids"]:
            self.collection.delete(ids=results["ids"])
            self.logger.debug(f"ChromaDB: 删除 {len(results['ids'])} chunks (item={item_id})")

    def search(self, query_embedding: list[float], top_k: int = 10) -> list[dict]:
        """语义搜索"""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        if not results or not results["ids"] or not results["ids"][0]:
            return []

        items = []
        for i, doc_id in enumerate(results["ids"][0]):
            items.append({
                "id": doc_id,
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
        return items

    def count(self) -> int:
        """返回存储的 chunk 总数"""
        try:
            return self.collection.count()
        except Exception:
            return 0


def init_chroma(persist_dir: str) -> ChromaClient:
    """初始化 ChromaDB 客户端并确保集合存在"""
    client = ChromaClient(persist_dir)
    client.get_or_create()
    return client
