"""大嘴怪 — LLM 知识库问答引擎

RAG 全流程：问题嵌入 → ChromaDB 检索 → Prompt 拼装 → LLM 流式推理 → 引用溯源。
支持 Ollama 本地和 OpenAI 兼容 API 远程两种后端。
"""
import json
import re
import uuid
from typing import Optional, Generator, Callable

from core.logger import get_logger
from core.db import Database
from core.chroma_client import ChromaClient
from core.config import get_config

logger = get_logger()

# ── System Prompt ────────────────────────────────

SYSTEM_PROMPT = """你是「大嘴怪」，用户的私人知识管家。你负责基于用户收藏和投喂的内容回答问题。

规则：
1. 严格基于下方【知识库检索结果】中的内容回答。不要编造信息。
2. 如果知识库中没有相关信息，诚实地说「我还没吃过相关内容，暂时无法回答。你可以投喂相关资料给我。」
3. 回答简洁有条理，要点化呈现。
4. 回答末尾标注引用的来源文件（标题 + 文件路径）。
5. 如果引用多个来源，用编号列出。
6. 用中文回答。"""

USER_PROMPT_TEMPLATE = """【知识库检索结果】

{context}

---

【用户问题】
{question}

请基于以上知识库内容回答。"""


class KbQA:
    """知识库问答引擎"""

    def __init__(self, db: Database, chroma: ChromaClient = None):
        self.db = db
        self.chroma = chroma
        self.config = get_config()
        self._embedding_model = None  # 延迟加载

    # ── 嵌入模型 ──────────────────────────────────

    @property
    def embedding_model(self):
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                model_name = self.config.embedding_model
                self._embedding_model = SentenceTransformer(model_name)
                logger.info(f"嵌入模型已加载: {model_name}")
            except ImportError:
                logger.warning("sentence-transformers 不可用，语义检索降级")
                self._embedding_model = None
            except Exception as e:
                logger.warning(f"嵌入模型加载失败: {e}")
                self._embedding_model = None
        return self._embedding_model

    # ── 主问答入口 ────────────────────────────────

    def ask(self, question: str, top_k: int = None,
            stream_callback: Callable[[str], None] = None,
            on_sources: Callable[[list[dict]], None] = None) -> str:
        """
        对知识库提问。
        - stream_callback(token): 每收到一个 token 调用一次
        - on_sources(sources): 检索完成后调用，传入引用来源列表
        返回完整回答文本。
        """
        if top_k is None:
            top_k = self.config.max_context_chunks

        # 1. 检索相关文档
        sources = self._retrieve(question, top_k)
        if on_sources:
            on_sources(sources)

        if not sources:
            msg = "我还没吃过相关内容，暂时无法回答。你可以投喂相关资料给我。🦖"
            if stream_callback:
                stream_callback(msg)
            return msg

        # 2. 拼装 Prompt
        context = self._build_context(sources)
        prompt = USER_PROMPT_TEMPLATE.format(context=context, question=question)

        # 3. LLM 推理
        full_answer = self._llm_stream(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            stream_callback=stream_callback,
        )

        # 4. 追加引用来源
        citation = self._build_citation(sources)
        full_answer_with_cite = full_answer.rstrip() + "\n\n" + citation

        if stream_callback:
            stream_callback("\n\n" + citation)  # 流式追加引用

        return full_answer_with_cite

    # ── 检索 ──────────────────────────────────────

    def _retrieve(self, question: str, top_k: int) -> list[dict]:
        """
        检索相关文档片段，返回去重排序后的来源列表。
        每个来源含: item_id, title, category, file_path, snippet, score
        """
        # FTS5 关键词搜索
        fts_results = self.db.search_fts(question, top_k * 2)
        logger.debug(f"FTS5 检索: {len(fts_results)} 条")

        # ChromaDB 语义搜索
        vector_results = []
        if self.chroma and self.embedding_model:
            try:
                query_embedding = self.embedding_model.encode([question])[0].tolist()
                raw = self.chroma.search(query_embedding, top_k)
                for r in raw:
                    meta = r.get("metadata", {})
                    vector_results.append({
                        "item_id": meta.get("item_id", ""),
                        "snippet": r.get("document", "")[:500],
                        "score": 1.0 - min(r.get("distance", 1.0), 2.0) / 2.0,
                        "source_type": "vector",
                    })
                logger.debug(f"语义检索: {len(vector_results)} 条")
            except Exception as e:
                logger.warning(f"语义检索失败: {e}")

        # 合并去重
        merged: dict[str, dict] = {}
        for r in fts_results:
            item_id = r["id"]
            merged[item_id] = {
                "item_id": item_id,
                "title": r["title"],
                "category": r["category"],
                "file_path": r.get("repo_path", ""),
                "type": r["type"],
                "snippet": (r.get("text_content", "") or "")[:500],
                "score": 0.6,  # FTS5 基础分
                "source_type": "fts",
            }

        for vr in vector_results:
            item_id = vr["item_id"]
            if not item_id:
                continue
            if item_id in merged:
                merged[item_id]["score"] = max(merged[item_id]["score"], vr["score"])
                merged[item_id]["source_type"] = "hybrid"
                if vr.get("snippet"):
                    merged[item_id]["snippet"] = vr["snippet"]
            else:
                # 从 DB 补全信息
                item = self.db.get_item(item_id)
                if item:
                    merged[item_id] = {
                        "item_id": item_id,
                        "title": item["title"],
                        "category": item["category"],
                        "file_path": item.get("repo_path", ""),
                        "type": item["type"],
                        "snippet": vr.get("snippet", ""),
                        "score": vr["score"],
                        "source_type": "vector",
                    }

        # 按分数排序，取 top_k
        sorted_sources = sorted(
            merged.values(), key=lambda x: x["score"], reverse=True
        )[:top_k]

        return sorted_sources

    def _build_context(self, sources: list[dict]) -> str:
        """构建检索上下文文本"""
        parts = []
        for i, s in enumerate(sources, 1):
            parts.append(
                f"[来源{i}] {s['title']} ({s.get('file_path', '')})\n"
                f"{s['snippet']}\n"
            )
        return "\n---\n".join(parts)

    def _build_citation(self, sources: list[dict]) -> str:
        """构建引用来源标注"""
        if not sources:
            return ""
        lines = ["📚 **引用来源：**"]
        for i, s in enumerate(sources, 1):
            lines.append(f"  {i}. {s['title']} — `{s.get('file_path', '')}`")
        return "\n".join(lines)

    # ── LLM 调用 ──────────────────────────────────

    def _llm_stream(self, system_prompt: str, user_prompt: str,
                    stream_callback: Callable[[str], None] = None) -> str:
        """根据配置选择 LLM 后端并流式调用"""
        backend = self.config.llm_backend
        if backend == "ollama":
            return self._ollama_stream(system_prompt, user_prompt, stream_callback)
        else:
            return self._openai_stream(system_prompt, user_prompt, stream_callback)

    def _ollama_stream(self, system_prompt: str, user_prompt: str,
                       stream_callback: Callable[[str], None] = None) -> str:
        """Ollama 本地推理（流式）"""
        import httpx

        endpoint = f"{self.config.ollama_endpoint}/api/chat"
        model = self.config.ollama_model

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": True,
            "options": {"temperature": 0.7, "num_predict": 2048},
        }

        full_text = ""
        try:
            with httpx.stream("POST", endpoint, json=payload, timeout=120.0) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            full_text += token
                            if stream_callback:
                                stream_callback(token)
                    except json.JSONDecodeError:
                        continue
        except httpx.ConnectError:
            logger.warning(f"Ollama 连接失败: {endpoint}")
            msg = f"无法连接到本地 Ollama ({endpoint})。请确认 Ollama 已启动。"
            if stream_callback:
                stream_callback(msg)
            return msg
        except Exception as e:
            logger.warning(f"Ollama 调用异常: {e}")
            msg = f"LLM 调用失败: {e}"
            if stream_callback:
                stream_callback(msg)
            return msg

        return full_text

    def _openai_stream(self, system_prompt: str, user_prompt: str,
                       stream_callback: Callable[[str], None] = None) -> str:
        """OpenAI 兼容 API 远程推理（流式）"""
        try:
            from openai import OpenAI

            client = OpenAI(
                base_url=self.config.api_endpoint,
                api_key=self.config.api_key,
                timeout=120.0,
            )

            full_text = ""
            stream = client.chat.completions.create(
                model=self.config.api_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=2048,
                stream=True,
            )

            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    token = delta.content
                    full_text += token
                    if stream_callback:
                        stream_callback(token)

            return full_text

        except ImportError:
            msg = "openai 库不可用。请安装: pip install openai"
            logger.warning(msg)
            if stream_callback:
                stream_callback(msg)
            return msg
        except Exception as e:
            logger.warning(f"API 调用异常: {e}")
            msg = f"API 调用失败: {e}"
            if stream_callback:
                stream_callback(msg)
            return msg

    # ── 对话历史 ──────────────────────────────────

    def save_conversation(self, session_id: str, role: str, content: str,
                          sources: list[dict] = None) -> None:
        """保存一轮对话"""
        sources_json = json.dumps(sources or [], ensure_ascii=False)
        self.db.execute(
            """INSERT INTO conversation_history (session_id, role, content, sources_json)
               VALUES (?, ?, ?, ?)""",
            (session_id, role, content, sources_json),
        )
        self.db.commit()

    def get_conversation(self, session_id: str, limit: int = None) -> list[dict]:
        """获取对话历史"""
        if limit is None:
            limit = self.config.max_history_rounds * 2
        rows = self.db.execute(
            """SELECT * FROM conversation_history
               WHERE session_id = ?
               ORDER BY created_at ASC LIMIT ?""",
            (session_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def new_session(self) -> str:
        return str(uuid.uuid4())


# ── 便捷工厂函数 ──────────────────────────────────

def create_kb_qa(db: Database, chroma: ChromaClient = None) -> KbQA:
    return KbQA(db, chroma)
