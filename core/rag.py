"""Consolidated RAG Engine: Loaders, Qdrant Vector Store, BM25, Reranking & LangGraph Agent Pipeline."""

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Any, Callable, Optional, TypedDict

import numpy as np
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from nemoguardrails import LLMRails, RailsConfig
from qdrant_client import QdrantClient, models
from langchain_qdrant import QdrantVectorStore

from core.config import get_runtime_config

logger = logging.getLogger("rag")


# ---------------------------------------------------------------------------
# Singletons & Qdrant Client Manager
# ---------------------------------------------------------------------------

_qdrant_clients: dict[str, QdrantClient] = {}


def get_qdrant_client(persist_directory: str) -> QdrantClient:
    """Return a singleton QdrantClient for a path to prevent concurrent lock errors."""
    abs_path = os.path.abspath(persist_directory)
    if abs_path not in _qdrant_clients:
        _qdrant_clients[abs_path] = QdrantClient(path=abs_path)
    return _qdrant_clients[abs_path]


def get_qdrant_vector_store(persist_directory: str, embedding=None) -> QdrantVectorStore:
    """Get or initialize a QdrantVectorStore using the singleton QdrantClient."""
    client = get_qdrant_client(persist_directory)
    existing = [c.name for c in client.get_collections().collections]
    if "documents" not in existing:
        client.create_collection(
            collection_name="documents",
            vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
        )
    return QdrantVectorStore(
        client=client,
        collection_name="documents",
        embedding=embedding or _get_embeddings(),
    )


# ---------------------------------------------------------------------------
# Lazy Singletons for Heavy ML Models
# ---------------------------------------------------------------------------

_embeddings_instance = None
_cross_encoder_instance = None
_rails_instance = None
_fallback_llm = None
_fallback_llm_model = None


def _get_embeddings():
    global _embeddings_instance
    if _embeddings_instance is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _embeddings_instance = HuggingFaceEmbeddings(
            model_name="BAAI/bge-small-en-v1.5",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings_instance


def _get_cross_encoder():
    global _cross_encoder_instance
    if _cross_encoder_instance is None:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder_instance = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2")
            logger.info("Cross-encoder reranker loaded")
        except Exception as exc:
            logger.warning("Cross-encoder not available: %s", exc)
            _cross_encoder_instance = False
    return _cross_encoder_instance if _cross_encoder_instance is not False else None


def _get_rails():
    global _rails_instance
    if _rails_instance is None:
        try:
            config_path = os.path.join(os.path.dirname(__file__), "guardrails_config")
            if not os.path.exists(config_path):
                config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "guardrails_config")
            config = RailsConfig.from_path(config_path)
            _rails_instance = LLMRails(config)
            logger.info("NeMo Guardrails loaded")
        except Exception as exc:
            logger.warning("Failed to load Guardrails: %s", exc)
            _rails_instance = False
    return _rails_instance if _rails_instance is not False else None


def _get_text_splitter():
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    return RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )


def get_active_model_name() -> str:
    return get_runtime_config()["groq_model"]


def _get_fallback_llm():
    global _fallback_llm, _fallback_llm_model
    config = get_runtime_config()
    target_model = config["openrouter_model"]

    if _fallback_llm is None or _fallback_llm_model != target_model:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            root_env = Path(__file__).resolve().parent.parent / ".env"
            if root_env.exists():
                from dotenv import load_dotenv
                load_dotenv(dotenv_path=root_env)
                api_key = os.environ.get("OPENROUTER_API_KEY")
        if api_key:
            from langchain_openai import ChatOpenAI
            _fallback_llm = ChatOpenAI(
                model=target_model,
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                max_tokens=config.get("max_tokens", 700),
                temperature=0.0,
            )
            _fallback_llm_model = target_model
            logger.info("Fallback LLM (OpenRouter) initialized with model %s", target_model)
    return _fallback_llm


# ---------------------------------------------------------------------------
# LLM Invocation with Exponential Backoff
# ---------------------------------------------------------------------------

def _is_rate_limit_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "rate_limit" in msg or "too many requests" in msg


def _retry_after_seconds(exc: Exception, default: float = 1.0) -> float:
    match = re.search(r"try again in (\d+(?:\.\d+)?)s", str(exc), re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return default


async def _invoke_with_backoff(llm, messages, tools=None, max_retries=3):
    import random
    delay = 1.0
    last_exc = None
    for attempt in range(max_retries):
        try:
            if tools:
                return await llm.bind_tools(tools).ainvoke(messages)
            return await llm.ainvoke(messages)
        except Exception as e:
            last_exc = e
            if _is_rate_limit_error(e) and attempt < max_retries - 1:
                wait = _retry_after_seconds(e, delay) + random.uniform(0, 0.5)
                logger.warning("Groq 429 — backing off %.1fs (attempt %d/%d)", wait, attempt + 1, max_retries)
                await asyncio.sleep(wait)
                delay *= 2
                continue
            raise
    raise last_exc


async def _invoke_llm(primary_llm, messages, tools=None):
    """Invoke LLM with 429 backoff, then automatic fallback to OpenRouter on failure."""
    try:
        return await _invoke_with_backoff(primary_llm, messages, tools=tools)
    except Exception as e:
        if _is_rate_limit_error(e):
            logger.warning("Groq rate limit hit (429), switching to OpenRouter: %s", e)
        else:
            logger.warning("Primary LLM failed (%s), falling back to OpenRouter: %s", type(e).__name__, e)
        fallback = _get_fallback_llm()
        if fallback:
            try:
                if tools:
                    return await fallback.bind_tools(tools).ainvoke(messages)
                return await fallback.ainvoke(messages)
            except Exception as fallback_err:
                if tools:
                    logger.warning("Fallback tool calling failed, retrying without tools: %s", fallback_err)
                    return await fallback.ainvoke(messages)
                raise
        raise


# ---------------------------------------------------------------------------
# Document Loaders & Ingestion (Delegated to deep core.ingestion module)
# ---------------------------------------------------------------------------

from core.ingestion import (
    IngestionEngine,
    compute_file_hash as _compute_file_hash,
    load_file_hashes as _load_file_hashes,
    save_file_hashes as _save_file_hashes,
    enrich_chunks as _enrich_chunks,
    load_documents,
    load_url,
    save_corpus as _save_corpus,
)


def _hash_file_path(persist_directory: str) -> Path:
    return IngestionEngine.hash_file_path(persist_directory)


async def _batch_add_documents(vector_store, chunks: list[Document], batch_size: int = 50, progress_callback=None):
    await IngestionEngine.batch_add_documents(vector_store, chunks, batch_size=batch_size, progress_callback=progress_callback)



# ---------------------------------------------------------------------------
# BM25 Keyword Search
# ---------------------------------------------------------------------------

class BM25Index:
    def __init__(self, corpus_path: Path):
        self.corpus_path = corpus_path
        self.texts: list[str] = []
        self.metadatas: list[dict] = []
        self.doc_len: list[int] = []
        self.avgdl: float = 0.0
        self.df: dict[str, int] = defaultdict(int)
        self.idf: dict[str, float] = {}
        self.tf: list[dict[str, int]] = []
        self._load()

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())

    def _load(self):
        if not self.corpus_path.exists():
            return
        with open(self.corpus_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                tokens = self._tokenize(data["text"])
                self.texts.append(data["text"])
                self.metadatas.append(data.get("metadata", {}))
                self.doc_len.append(len(tokens))
                tf_dict = defaultdict(int)
                for t in tokens:
                    tf_dict[t] += 1
                self.tf.append(dict(tf_dict))
                for t in set(tokens):
                    self.df[t] += 1

        n_docs = len(self.texts)
        if n_docs > 0:
            self.avgdl = sum(self.doc_len) / n_docs
            for term, freq in self.df.items():
                self.idf[term] = np.log((n_docs - freq + 0.5) / (freq + 0.5) + 1.0)

    def search(self, query: str, k: int = 10) -> list[tuple[int, float]]:
        tokens = self._tokenize(query)
        if not tokens or not self.texts:
            return []
        scores = np.zeros(len(self.texts))
        k1 = 1.5
        b = 0.75
        for t in tokens:
            idf_val = self.idf.get(t, 0.0)
            if idf_val <= 0:
                continue
            for i, tf_dict in enumerate(self.tf):
                tf_val = tf_dict.get(t, 0)
                if tf_val > 0:
                    numerator = tf_val * (k1 + 1)
                    denominator = tf_val + k1 * (1 - b + b * (self.doc_len[i] / (self.avgdl or 1.0)))
                    scores[i] += idf_val * (numerator / denominator)

        ranked_indices = np.argsort(scores)[::-1]
        results = []
        for idx in ranked_indices:
            if scores[idx] > 0:
                results.append((int(idx), float(scores[idx])))
            if len(results) >= k:
                break
        return results


_bm25_cache: dict[str, tuple[float, BM25Index]] = {}


def _get_bm25(persist_directory: str) -> BM25Index | None:
    corpus_path = Path(persist_directory) / "bm25_corpus.jsonl"
    if not corpus_path.exists():
        return None
    mtime = corpus_path.stat().st_mtime
    if persist_directory in _bm25_cache:
        cached_mtime, index = _bm25_cache[persist_directory]
        if cached_mtime == mtime:
            return index
    index = BM25Index(corpus_path)
    _bm25_cache[persist_directory] = (mtime, index)
    return index


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Deep HybridRetriever Module: Dense + BM25 + RRF + Cross-Encoder Reranking
# ---------------------------------------------------------------------------

class HybridRetriever:
    """Deep retrieval module unifying dense Qdrant search, BM25 lexical search,
    Reciprocal Rank Fusion (RRF), and cross-encoder re-ranking behind a single interface.
    """

    def __init__(self, vector_store, session_dir: str = "", cross_encoder=None):
        self.vector_store = vector_store
        self.session_dir = session_dir
        self._cross_encoder = cross_encoder

    @property
    def cross_encoder(self):
        if self._cross_encoder is not None:
            return self._cross_encoder if self._cross_encoder is not False else None
        return _get_cross_encoder()

    async def ahybrid_search(
        self,
        query: str,
        k: int = 10,
        filter_sources: list[str] | None = None,
    ) -> list[Document]:
        norm_filters = {s.strip().lower() for s in filter_sources if s and s.strip()} if filter_sources else None

        def _matches_filter(source_name: str) -> bool:
            if not norm_filters:
                return True
            s_lower = source_name.strip().lower()
            return any(
                f == s_lower
                or s_lower.endswith("/" + f)
                or s_lower.endswith("\\" + f)
                or Path(s_lower).name == Path(f).name
                for f in norm_filters
            )

        async def _search_semantic():
            try:
                fetch_k = k * 4 if norm_filters else k * 2
                retriever = self.vector_store.as_retriever(search_kwargs={"k": fetch_k})
                docs = await retriever.ainvoke(query)
                if norm_filters:
                    docs = [d for d in docs if _matches_filter(d.metadata.get("source_name", ""))]
                return docs[: k * 2]
            except Exception as exc:
                logger.warning("Semantic search failed: %s", exc)
                return []

        async def _search_bm25():
            try:
                bm25 = _get_bm25(self.session_dir)
                if bm25 is not None:
                    hits = bm25.search(query, k=k * 4 if norm_filters else k * 2)
                    if norm_filters and hits:
                        filtered = []
                        for idx, score in hits:
                            if idx < len(bm25.metadatas):
                                if _matches_filter(bm25.metadatas[idx].get("source_name", "")):
                                    filtered.append((idx, score))
                        hits = filtered[: k * 2]
                    return bm25, hits
            except Exception as exc:
                logger.warning("BM25 search failed: %s", exc)
            return None, []

        semantic_docs, (bm25, bm25_hits) = await asyncio.gather(_search_semantic(), _search_bm25())

        bm25_results = {}
        semantic_results = {}

        if bm25_hits:
            for rank, (idx, _) in enumerate(bm25_hits):
                bm25_results[idx] = rank

        for rank, doc in enumerate(semantic_docs):
            key = doc.page_content[:200]
            semantic_results[key] = (rank, doc)

        rrf_scores: dict[str, float] = {}
        doc_map: dict[str, Document] = {}
        k_rrf = 60

        if bm25 is not None and bm25_results:
            for idx, rank in bm25_results.items():
                text = bm25.texts[idx]
                key = text[:200]
                rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k_rrf + rank + 1)
                doc_map[key] = Document(page_content=text, metadata=bm25.metadatas[idx])

        for key, (rank, doc) in semantic_results.items():
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k_rrf + rank + 1)
            if key not in doc_map:
                doc_map[key] = doc

        sorted_keys = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        return [doc_map[key] for key in sorted_keys[:k]]

    async def aretrieve(
        self,
        query: str,
        top_k: int = 6,
        filter_sources: list[str] | None = None,
        is_comparative: bool = False,
    ) -> list[Document]:
        sources_list = [s for s in (filter_sources or []) if s and s.strip()]

        if is_comparative and not sources_list and self.session_dir:
            bm25 = _get_bm25(self.session_dir)
            if bm25 and bm25.metadatas:
                discovered = list({m.get("source_name") for m in bm25.metadatas if m.get("source_name")})
                if len(discovered) >= 2:
                    sources_list = discovered

        ce = self.cross_encoder

        if len(sources_list) >= 2:
            tasks = [
                self.ahybrid_search(query, k=top_k, filter_sources=[src])
                for src in sources_list
            ]
            results_per_source = await asyncio.gather(*tasks)

            final_docs = []
            allocation = max(2, top_k // len(sources_list))

            for src, src_docs in zip(sources_list, results_per_source):
                if not src_docs:
                    continue
                if ce and len(src_docs) > 1:
                    pairs = [(query, doc.page_content) for doc in src_docs]
                    scores = await asyncio.to_thread(ce.predict, pairs)
                    scored_docs = sorted(zip(scores, src_docs), key=lambda x: x[0], reverse=True)
                    final_docs.extend([doc for _, doc in scored_docs[:allocation]])
                else:
                    final_docs.extend(src_docs[:allocation])

            docs = final_docs
            if not docs:
                docs = await self.ahybrid_search(query, k=10, filter_sources=None)
        else:
            docs = await self.ahybrid_search(query, k=10, filter_sources=filter_sources)
            if not docs and filter_sources:
                logger.info("Targeted retrieval returned 0 docs; falling back to unfiltered search")
                docs = await self.ahybrid_search(query, k=10, filter_sources=None)

            if docs and ce and len(docs) > 1:
                pairs = [(query, doc.page_content) for doc in docs]
                scores = await asyncio.to_thread(ce.predict, pairs)
                scored_docs = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
                docs = [doc for _, doc in scored_docs[:top_k]]
            elif docs:
                docs = docs[:top_k]

        return docs

    def retrieve(
        self,
        query: str,
        top_k: int = 6,
        filter_sources: list[str] | None = None,
        is_comparative: bool = False,
    ) -> list[Document]:
        """Synchronous convenience call for retrieve."""
        return asyncio.run(
            self.aretrieve(query, top_k=top_k, filter_sources=filter_sources, is_comparative=is_comparative)
        )

    async def search_and_format(
        self,
        query: str,
        top_k: int = 6,
        filter_sources: list[str] | None = None,
        is_comparative: bool = False,
    ) -> str:
        docs = await self.aretrieve(
            query, top_k=top_k, filter_sources=filter_sources, is_comparative=is_comparative
        )
        if not docs:
            return "No relevant documents found. The document content could not be retrieved."

        parts = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source_name", "unknown")
            page = doc.metadata.get("page_number") or doc.metadata.get("page")
            if isinstance(page, int) and doc.metadata.get("source_type") == "pdf" and "page_number" not in doc.metadata:
                page = page + 1
            page_str = f" | Page {page}" if page not in (None, "") else ""
            parts.append(f"[Document {i}: {source}{page_str}]\n{doc.page_content}")

        return "\n\n".join(parts)


async def ahybrid_search(
    query: str,
    vector_store,
    persist_directory: str,
    k: int = 10,
    filter_sources: list[str] | None = None,
) -> list[Document]:
    """Combine BM25 keyword matching with dense vector similarity via Reciprocal Rank Fusion."""
    retriever = HybridRetriever(vector_store, session_dir=persist_directory)
    return await retriever.ahybrid_search(query, k=k, filter_sources=filter_sources)


def get_hybrid_retriever(vector_store, session_dir: str = "", cross_encoder=None) -> HybridRetriever:
    """Return a deep HybridRetriever instance."""
    return HybridRetriever(vector_store, session_dir=session_dir, cross_encoder=cross_encoder)


def create_hybrid_retriever_tool(
    vector_store,
    session_dir: str = "",
    filter_sources: list[str] | None = None,
    is_comparative: bool = False,
):
    """Create a LangChain tool wrapping the deep HybridRetriever."""
    retriever = get_hybrid_retriever(vector_store, session_dir=session_dir)

    @tool
    async def search_documents(query: str) -> str:
        """Search uploaded documents for specific information with multi-source balance."""
        return await retriever.search_and_format(
            query, filter_sources=filter_sources, is_comparative=is_comparative
        )

    return search_documents


# ---------------------------------------------------------------------------
# High-Level Processing Pipelines
# ---------------------------------------------------------------------------

async def process_uploaded_files(
    uploaded_files,
    existing_store=None,
    persist_directory="./qdrant_db",
    progress_callback=None,
    force: bool = False,
):
    return await IngestionEngine.ingest_files(
        uploaded_files,
        existing_store=existing_store,
        persist_directory=persist_directory,
        progress_callback=progress_callback,
        force=force,
        embeddings=_get_embeddings(),
        vector_store_factory=get_qdrant_vector_store,
        text_splitter=_get_text_splitter(),
    )


async def process_url(
    url: str,
    existing_store=None,
    persist_directory="./qdrant_db",
    progress_callback=None,
):
    return await IngestionEngine.ingest_url(
        url,
        existing_store=existing_store,
        persist_directory=persist_directory,
        progress_callback=progress_callback,
        embeddings=_get_embeddings(),
        vector_store_factory=get_qdrant_vector_store,
        text_splitter=_get_text_splitter(),
    )



# ---------------------------------------------------------------------------
# LangGraph Agent Workflow
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    file_names: Optional[list]
    url_names: Optional[list]
    retrieved_docs: list
    sources: list
    model_call_count: int
    max_model_calls: int
    blocked_reason: Optional[str]
    context_used: Optional[str]
    agent_path: Optional[str]
    is_comparative: Optional[bool]


def _to_langchain_messages(messages):
    converted = []
    for msg in messages:
        if isinstance(msg, BaseMessage):
            converted.append(msg)
        elif isinstance(msg, dict):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                converted.append(SystemMessage(content=content))
            elif role == "assistant":
                converted.append(AIMessage(content=content))
            else:
                converted.append(HumanMessage(content=content))
        else:
            converted.append(HumanMessage(content=str(msg)))
    return converted


async def check_input(state: AgentState) -> dict:
    last_message = state["messages"][-1]
    user_text = getattr(last_message, "content", str(last_message))

    _harmless = [
        "summarize", "explain", "what", "how", "who", "when", "where",
        "tell me", "describe", "list", "define", "compare", "analyze",
        "hello", "hi", "hey", "thanks", "thank you", "yes", "no",
    ]
    _suspicious = [
        "ignore", "disregard", "forget", "override", "bypass", "jailbreak",
        "system prompt", "your instructions", "your prompt", "your rules",
        "instead say", "pretend", "act as", "roleplay", "role-play",
        "you are now", "new instructions", "developer mode", "dan mode",
        "reveal", "repeat the words", "repeat everything", "print your",
        "output your", "api key", "password", "secret",
    ]
    lower = user_text.lower()
    if any(lower.startswith(p) for p in _harmless) and not any(kw in lower for kw in _suspicious) and len(user_text) < 200:
        return {"blocked_reason": None}

    rails = _get_rails()
    if rails is not None:
        try:
            response = await asyncio.to_thread(rails.generate, messages=[{"role": "user", "content": user_text}])
            blocked_phrases = ["cannot process", "not allowed", "i'm sorry", "i cannot", "i can't", "not able to"]
            if any(p in response["content"].lower() for p in blocked_phrases):
                return {
                    "blocked_reason": "Input blocked by safety guardrails",
                    "messages": [AIMessage(content=response["content"])],
                }
        except Exception as exc:
            logger.warning("Guardrails check failed (allowing message): %s", exc)

    return {"blocked_reason": None}


def rate_limit_check(state: AgentState) -> dict:
    current_count = state.get("model_call_count", 0) + 1
    max_calls = state.get("max_model_calls", 5)
    if current_count > max_calls:
        return {
            "model_call_count": current_count,
            "messages": [AIMessage(content=f"Reached maximum reasoning steps ({max_calls}). Here is what I found so far.")],
        }
    return {"model_call_count": current_count}


def build_agent_graph(vector_store, session_dir: str = ""):
    """Build the agentic RAG graph with forced retrieval when docs exist."""
    if vector_store is None and session_dir:
        db_path = Path(session_dir) / "qdrant_db"
        if db_path.exists():
            try:
                vector_store = get_qdrant_vector_store(str(db_path))
            except Exception as exc:
                logger.warning("Could not auto-load vector store: %s", exc)

    has_documents = vector_store is not None
    search_tool = create_hybrid_retriever_tool(vector_store, session_dir) if has_documents else None

    config = get_runtime_config()
    llm = ChatGroq(
        model=get_active_model_name(),
        api_key=os.environ.get("GROQ_API_KEY"),
        max_tokens=config.get("max_tokens", 700),
        temperature=0.0,
    )

    async def agent_decision(state: AgentState):
        if has_documents:
            return {"agent_path": "retrieval"}

        system_msg = SystemMessage(
            content=(
                "You are a helpful assistant. No documents have been uploaded yet. "
                "Answer all questions from your own knowledge. "
                "If the user asks about a specific document, let them know they need to upload files first. "
                "NEVER say 'sorry' or apologize."
            )
        )
        messages = [system_msg] + _to_langchain_messages(state["messages"])
        try:
            response = await _invoke_llm(llm, messages)
            return {"messages": [response], "agent_path": "direct"}
        except Exception as exc:
            logger.error("Agent decision failed: %s", exc)
            raise

    async def _rewrite_query_with_history(query: str, messages) -> str:
        history = []
        for msg in messages:
            if isinstance(msg, HumanMessage) and msg.content:
                history.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content:
                history.append(f"Assistant: {msg.content[:300]}")

        if sum(1 for h in history if h.startswith("User:")) < 2:
            return query

        query_words = set(query.lower().split())
        pronouns = {"it", "its", "they", "them", "their", "this", "that", "these", "those", "he", "she", "his", "her", "previous", "above"}
        if len(query.split()) > 7 and not (query_words & pronouns):
            return query

        try:
            rewrite_llm = ChatGroq(
                model=get_active_model_name(),
                api_key=os.environ.get("GROQ_API_KEY"),
                max_tokens=60,
                temperature=0.0,
            )
            response = await _invoke_llm(rewrite_llm, [
                SystemMessage(content="Rewrite the user's latest question as a standalone search query for document retrieval. Return ONLY the rewritten query."),
                HumanMessage(content="Conversation so far:\n" + "\n".join(history[-6:-1]) + f"\n\nLatest question: {query}"),
            ])
            rewritten = getattr(response, "content", "").strip().strip('"')
            if 0 < len(rewritten) < 300:
                return rewritten
        except Exception as exc:
            logger.warning("Query rewrite failed, using original: %s", exc)
        return query

    async def force_retrieve(state: AgentState):
        if not has_documents:
            return {"messages": [], "context_used": "", "agent_path": "direct"}

        search_query = None
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage) and msg.content:
                search_query = msg.content
                break
            elif isinstance(msg, dict) and msg.get("role") == "user" and msg.get("content"):
                search_query = msg["content"]
                break

        if search_query:
            search_query = await _rewrite_query_with_history(search_query, state["messages"])
        if not search_query:
            search_query = "summarize the document"

        all_known_sources = list(state.get("file_names") or []) + list(state.get("url_names") or [])
        target_sources = None

        search_query_lower = search_query.lower()
        comparison_keywords = [
            "compare", "comparison", "difference", "differences", "versus", "vs", "vs.",
            "both", "either", "which one", "who has", "better", "pros and cons",
            "all documents", "all files", "both documents", "both files", "all sources",
        ]
        is_explicit_compare = any(kw in search_query_lower for kw in comparison_keywords)

        matched_sources = []
        for s in all_known_sources:
            stem = Path(s).stem.lower().replace("_", " ").replace("-", " ")
            stem_words = [w for w in stem.split() if len(w) > 3 and w not in {"guide", "reference", "complete", "resume"}]
            if Path(s).name.lower() in search_query_lower or stem in search_query_lower:
                matched_sources.append(s)
            elif any(w in search_query_lower for w in stem_words):
                matched_sources.append(s)

        is_multi_source = is_explicit_compare or len(matched_sources) >= 2 or (len(all_known_sources) >= 2 and is_explicit_compare)

        if is_multi_source:
            if len(matched_sources) >= 2:
                target_sources = matched_sources
            elif all_known_sources:
                target_sources = all_known_sources
            else:
                target_sources = None
        else:
            current_turn_files = []
            for msg in reversed(state["messages"]):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    current_turn_files = [f.get("name") for f in msg.get("files", []) if isinstance(f, dict) and f.get("name")]
                    break
                elif isinstance(msg, HumanMessage):
                    files_list = getattr(msg, "additional_kwargs", {}).get("files", [])
                    current_turn_files = [f.get("name") for f in files_list if isinstance(f, dict) and f.get("name")]
                    break

            if current_turn_files:
                target_sources = current_turn_files
            elif matched_sources and len(matched_sources) < len(all_known_sources):
                target_sources = matched_sources
            else:
                target_sources = None

        active_search_tool = create_hybrid_retriever_tool(
            vector_store,
            session_dir,
            filter_sources=target_sources,
            is_comparative=is_multi_source,
        )
        try:
            context = await active_search_tool.ainvoke(search_query)
        except Exception as exc:
            logger.error("Forced retrieval failed: %s", exc)
            context = "Retrieval failed."

        return {
            "messages": [],
            "context_used": context,
            "agent_path": "retrieval",
            "retrieved_docs": [context],
            "is_comparative": is_multi_source,
        }

    async def respond(state: AgentState):
        context_used = state.get("context_used", "")
        is_comparative = state.get("is_comparative", False)

        if context_used and context_used != "No relevant documents found.":
            if is_comparative:
                prompt = (
                    "You are an enterprise AI research assistant performing a multi-document synthesis and comparison.\n\n"
                    "INSTRUCTIONS:\n"
                    "1. Ground your analysis EXCLUSIVELY on the retrieved context below. Do NOT assume unstated facts.\n"
                    "2. Provide a clear, structured side-by-side Markdown comparison table covering key dimensions (e.g. roles, experience, tech stack, policies).\n"
                    "3. Cite specific document names and page numbers in parentheses when stating facts (e.g., `(Bilal_Resume.pdf, p. 1)`).\n"
                    "4. If a document does NOT state an item or has missing data, explicitly write 'Not mentioned in document' in the table/text.\n"
                    "5. Conclude with a concise synthesis highlighting key differences and actionable takeaways.\n"
                    "6. Do NOT append a separate 'Sources' list at the very end — sources are handled by the UI.\n\n"
                    f"=== RETRIEVED CONTEXT ===\n{context_used}\n=========================="
                )
            else:
                prompt = (
                    "You are an enterprise AI research assistant.\n\n"
                    "INSTRUCTIONS:\n"
                    "1. Answer the user's question directly, accurately, and thoroughly based EXCLUSIVELY on the retrieved context below.\n"
                    "2. Include page-level citations in parentheses where available (e.g., `(Document.pdf, p. 1)`).\n"
                    "3. Format your response cleanly using headings and bullet points for readability.\n"
                    "4. If the retrieved context does not contain enough information to fully answer, state clearly what is known and what is missing.\n"
                    "5. Do NOT list sources at the end — they are displayed separately by the UI.\n\n"
                    f"=== RETRIEVED CONTEXT ===\n{context_used}\n=========================="
                )
        else:
            prompt = (
                "No document context was retrieved. Answer using your general knowledge, "
                "but clearly state that the answer is NOT based on uploaded documents. "
                "NEVER say 'sorry' or apologize."
            )

        latest_user = None
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage) and msg.content:
                latest_user = msg
                break
            elif isinstance(msg, dict) and msg.get("role") == "user" and msg.get("content"):
                latest_user = HumanMessage(content=msg["content"])
                break

        messages = [SystemMessage(content=prompt)] + ([latest_user] if latest_user else [])
        response = await _invoke_llm(llm, messages)
        return {"messages": [response], "agent_path": "retrieval"}

    workflow = StateGraph(AgentState)
    workflow.add_node("check_input", check_input)
    workflow.add_node("rate_limit_check", rate_limit_check)
    workflow.add_node("agent_decision", agent_decision)
    workflow.add_node("force_retrieve", force_retrieve)
    workflow.add_node("respond", respond)

    workflow.add_edge(START, "check_input")
    workflow.add_conditional_edges("check_input", lambda s: END if s.get("blocked_reason") else "rate_limit_check")
    workflow.add_conditional_edges("rate_limit_check", lambda s: END if s.get("model_call_count", 0) > s.get("max_model_calls", 5) else "agent_decision")
    workflow.add_conditional_edges("agent_decision", lambda s: "force_retrieve" if has_documents else END)
    workflow.add_edge("force_retrieve", "respond")
    workflow.add_edge("respond", END)

    return workflow.compile()


def extract_result_metadata(result: dict) -> tuple[str, dict]:
    from core.ui import clean_response
    model_name = get_active_model_name()
    if not result:
        return "", {"model": model_name}

    messages = result.get("messages", [])
    agent_path = result.get("agent_path", "direct")
    context_used = result.get("context_used", "")

    answer = ""
    if messages:
        last_msg = messages[-1]
        answer = getattr(last_msg, "content", "") or (last_msg.get("content", "") if isinstance(last_msg, dict) else str(last_msg))

    sources = []
    seen = set()
    if context_used:
        for block in context_used.split("\n\n"):
            match = re.match(r"^\[(?:Source|Document)(?:\s+\d+)?: ([^\]]+)\]", block)
            if match:
                raw_src = match.group(1).strip()
                page_match = re.search(r"(?:\|\s*Page|\(page)\s*(\d+)\)?$", raw_src, re.IGNORECASE)
                if page_match:
                    page_num = page_match.group(1)
                    src_name = re.sub(r"\s*(?:\|\s*Page|\(page)\s*\d+\)?$", "", raw_src, flags=re.IGNORECASE).strip()
                    key = (src_name, page_num)
                    if key not in seen:
                        seen.add(key)
                        sources.append({"name": src_name, "page": page_num})
                else:
                    if raw_src not in seen:
                        seen.add(raw_src)
                        sources.append({"name": raw_src})

    metadata = {
        "model": model_name,
        "path": agent_path,
        "sources": sources,
        "chunks": len(sources) if sources else 0,
        "context_used": context_used,
    }
    return clean_response(answer), metadata


async def run_agent_pipeline(
    vector_store,
    messages: list[dict],
    file_names: list[str] | None = None,
    url_names: list[str] | None = None,
    session_dir: str = "",
    on_step: Optional[Callable[[int, str], None]] = None,
) -> tuple[str, dict]:
    """Execute the full agent workflow and return (answer, metadata)."""
    t0 = time.perf_counter()
    graph = build_agent_graph(vector_store, session_dir)

    initial_state = {
        "messages": _to_langchain_messages(messages),
        "file_names": file_names or [],
        "url_names": url_names or [],
        "retrieved_docs": [],
        "sources": [],
        "model_call_count": 0,
        "max_model_calls": 5,
        "blocked_reason": None,
        "context_used": "",
        "agent_path": None,
    }

    step_idx = 0
    final_output = {}
    async for event in graph.astream(initial_state, stream_mode="updates"):
        for node_name, node_output in event.items():
            step_idx += 1
            if on_step:
                on_step(step_idx, node_name)
            final_output.update(node_output)

    answer, metadata = extract_result_metadata(final_output)
    total_ms = int((time.perf_counter() - t0) * 1000)
    metadata["trace"] = {
        "total_ms": total_ms,
        "path": final_output.get("agent_path", "direct"),
        "blocked": bool(final_output.get("blocked_reason")),
    }
    return answer, metadata

# ---------------------------------------------------------------------------
# Evaluation Engine (Delegated to deep core.evaluation module)
# ---------------------------------------------------------------------------

from core.evaluation import EvaluationEngine, evaluate_ragas

