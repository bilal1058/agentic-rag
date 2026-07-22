import os
import re
import json
import hashlib
import tempfile
import logging
from pathlib import Path
from collections import defaultdict

import numpy as np
from langchain_community.document_loaders import (
    PyPDFLoader,
    UnstructuredMarkdownLoader,
    CSVLoader,
    WebBaseLoader,
    Docx2txtLoader,
    TextLoader,
    UnstructuredPowerPointLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import QdrantClient, models
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration — tuneable via environment variables
# ---------------------------------------------------------------------------

CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "200"))
EMBEDDING_BATCH_SIZE = int(os.environ.get("EMBEDDING_BATCH_SIZE", "500"))

# ---------------------------------------------------------------------------
# Singletons & Qdrant Client Manager
# ---------------------------------------------------------------------------

_embeddings = None
_qdrant_clients: dict[str, QdrantClient] = {}


def get_qdrant_client(persist_directory: str) -> QdrantClient:
    """Return a singleton QdrantClient for a path to prevent concurrent lock errors."""
    abs_path = str(Path(persist_directory).resolve())
    if abs_path not in _qdrant_clients:
        Path(abs_path).mkdir(parents=True, exist_ok=True)
        _qdrant_clients[abs_path] = QdrantClient(path=abs_path)
    return _qdrant_clients[abs_path]


def get_qdrant_vector_store(persist_directory: str, embedding=None) -> QdrantVectorStore:
    """Get or initialize a QdrantVectorStore using the singleton QdrantClient."""
    client = get_qdrant_client(persist_directory)
    if not client.collection_exists("rag_documents"):
        client.create_collection(
            collection_name="rag_documents",
            vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
        )
    if embedding is None:
        embedding = _get_embeddings()
    return QdrantVectorStore(
        client=client,
        collection_name="rag_documents",
        embedding=embedding,
    )


def _sanitize_text(text: str) -> str:
    """Replace problematic Unicode characters with safe alternatives."""
    replacements = {
        "\u2192": " -> ",   # →
        "\u2190": " <- ",   # ←
        "\u2194": " <-> ",  # ↔
        "\u2191": " ^ ",    # ↑
        "\u2193": " v ",    # ↓
        "\u2026": "...",    # …
        "\u2014": "--",     # —
        "\u2013": "-",      # –
        "\u2018": "'",      # '
        "\u2019": "'",      # '
        "\u201c": '"',      # "
        "\u201d": '"',      # "
        "\u2022": "-",      # •
        "\u25cf": "*",      # ●
        "\u25cb": "o",      # ○
        "\u2610": "[ ]",    # ☐
        "\u2611": "[x]",    # ☑
        "\u2612": "[x]",    # ☒
        "\u2713": "v",      # ✓
        "\u2717": "x",      # ✗
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Remove any remaining non-BMP characters (above U+FFFF)
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    return text


def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
    return _embeddings


def _get_text_splitter():
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )


def _bm25_tokenize(text: str) -> list[str]:
    return text.lower().split()


# ---------------------------------------------------------------------------
# JSONL-based BM25 corpus — scalable append-only storage
# ---------------------------------------------------------------------------

def _corpus_path_jsonl(persist_directory: str) -> Path:
    return Path(persist_directory) / "bm25_corpus.jsonl"


def _corpus_path_json(persist_directory: str) -> Path:
    """Legacy JSON path for backward compatibility."""
    return Path(persist_directory) / "bm25_corpus.json"


def _migrate_json_to_jsonl(persist_directory: str) -> bool:
    """Auto-migrate legacy bm25_corpus.json → bm25_corpus.jsonl.

    Returns True if migration happened (or was already done).
    """
    jsonl_path = _corpus_path_jsonl(persist_directory)
    if jsonl_path.exists():
        return True  # Already migrated

    # Check both possible legacy locations
    candidates = [
        _corpus_path_json(persist_directory),
        Path(persist_directory) / "chroma_db" / "bm25_corpus.json",
    ]
    legacy_path = None
    for p in candidates:
        if p.exists():
            legacy_path = p
            break

    if legacy_path is None:
        return False  # Nothing to migrate

    try:
        data = json.loads(legacy_path.read_text(encoding="utf-8"))
        texts = data.get("texts", [])
        metadatas = data.get("metadatas", [])
        if not texts:
            return False

        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for text, meta in zip(texts, metadatas):
                line = json.dumps({"text": text, "metadata": meta}, ensure_ascii=False)
                f.write(line + "\n")

        logger.info(
            "Migrated BM25 corpus %s → %s (%d chunks)",
            legacy_path, jsonl_path, len(texts),
        )
        return True
    except Exception as exc:
        logger.warning("BM25 corpus migration failed: %s", exc)
        return False


def _save_corpus(chunks: list[Document], persist_directory: str, append: bool = False):
    """Persist the BM25 corpus in JSONL format.

    With append=True, new chunks are appended (deduplicated by content hash).
    """
    jsonl_path = _corpus_path_jsonl(persist_directory)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    # If appending, load existing content hashes for dedup
    existing_hashes: set[str] = set()
    if append and jsonl_path.exists():
        for entry in _iter_corpus(persist_directory):
            existing_hashes.add(hashlib.md5(entry["text"].encode()).hexdigest())

    mode = "a" if append and jsonl_path.exists() else "w"

    if not append:
        # Full write — write all chunks
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for chunk in chunks:
                line = json.dumps(
                    {"text": chunk.page_content, "metadata": chunk.metadata},
                    ensure_ascii=False,
                )
                f.write(line + "\n")
    else:
        # Append only new, non-duplicate chunks
        new_count = 0
        with open(jsonl_path, "a", encoding="utf-8") as f:
            for chunk in chunks:
                h = hashlib.md5(chunk.page_content.encode()).hexdigest()
                if h not in existing_hashes:
                    line = json.dumps(
                        {"text": chunk.page_content, "metadata": chunk.metadata},
                        ensure_ascii=False,
                    )
                    f.write(line + "\n")
                    existing_hashes.add(h)
                    new_count += 1
        if new_count < len(chunks):
            logger.info(
                "Deduplication: %d/%d chunks were duplicates, skipped",
                len(chunks) - new_count, len(chunks),
            )

    # Invalidate BM25 cache for this directory
    _bm25_cache.pop(persist_directory, None)


def _iter_corpus(persist_directory: str):
    """Stream-parse the JSONL corpus, yielding {"text": ..., "metadata": ...} dicts."""
    # Try JSONL first
    jsonl_path = _corpus_path_jsonl(persist_directory)
    if jsonl_path.exists():
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
        return

    # Attempt auto-migration from legacy JSON
    if _migrate_json_to_jsonl(persist_directory):
        yield from _iter_corpus(persist_directory)
        return

    # Also check chroma_db subdirectory (session dirs sometimes use this layout)
    chroma_jsonl = Path(persist_directory) / "chroma_db" / "bm25_corpus.jsonl"
    if chroma_jsonl.exists():
        with open(chroma_jsonl, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
        return


def _load_corpus(persist_directory: str) -> dict | None:
    """Load the full corpus into memory (for BM25 init).

    Returns {"texts": [...], "metadatas": [...]} or None.
    """
    texts = []
    metadatas = []
    for entry in _iter_corpus(persist_directory):
        texts.append(entry["text"])
        metadatas.append(entry.get("metadata", {}))

    if not texts:
        return None
    return {"texts": texts, "metadatas": metadatas}


# ---------------------------------------------------------------------------
# BM25 retriever — Numpy-vectorized for scalability
# ---------------------------------------------------------------------------

_bm25_cache: dict[str, tuple[float, "BM25Retriever"]] = {}


class BM25Retriever:
    """BM25 retriever using an inverted index and numpy for sub-millisecond scoring.

    Pre-computes inverted index mappings and IDF values at init time,
    allowing query scoring to touch only matching documents.
    """

    def __init__(self, texts: list[str], metadatas: list[dict], k: int = 10):
        self.texts = texts
        self.metadatas = metadatas
        self.k = k
        self.N = len(texts)

        # Tokenize documents
        self.tokenized = [_bm25_tokenize(t) for t in texts]

        # Build vocab → index mapping
        vocab: dict[str, int] = {}
        for tokens in self.tokenized:
            for tok in tokens:
                if tok not in vocab:
                    vocab[tok] = len(vocab)
        self.vocab = vocab
        vocab_size = len(vocab)

        # Document lengths as numpy array
        self.doc_lengths = np.array([len(t) for t in self.tokenized], dtype=np.float32)
        self.avgdl = float(self.doc_lengths.mean()) if self.N > 0 else 1.0

        if self.N > 0 and vocab_size > 0:
            # Build inverted index: term_idx -> (doc_indices_array, tf_array)
            inv_docs: dict[int, list[int]] = defaultdict(list)
            inv_tfs: dict[int, list[float]] = defaultdict(list)
            df_counts = np.zeros(vocab_size, dtype=np.int32)

            for doc_i, tokens in enumerate(self.tokenized):
                counts: dict[int, int] = {}
                for tok in tokens:
                    idx = vocab[tok]
                    counts[idx] = counts.get(idx, 0) + 1

                for term_idx, count in counts.items():
                    inv_docs[term_idx].append(doc_i)
                    inv_tfs[term_idx].append(float(count))
                    df_counts[term_idx] += 1

            self.inverted_index: dict[int, tuple[np.ndarray, np.ndarray]] = {
                t_idx: (
                    np.array(inv_docs[t_idx], dtype=np.int32),
                    np.array(inv_tfs[t_idx], dtype=np.float32),
                )
                for t_idx in inv_docs
            }

            # Pre-compute IDF for all terms
            self.idf = np.log(
                (self.N - df_counts + 0.5) / (df_counts + 0.5) + 1.0
            ).astype(np.float32)
        else:
            self.inverted_index = {}
            self.idf = np.array([], dtype=np.float32)

    def search(self, query: str, k: int | None = None, filter_func=None) -> list[tuple[int, float]]:
        """Score matching documents against the query using an inverted index."""
        if self.N == 0:
            return []

        k = k or self.k
        k1 = 1.6
        b = 0.75

        query_tokens = _bm25_tokenize(query)
        query_term_indices = [self.vocab[t] for t in query_tokens if t in self.vocab]

        if not query_term_indices:
            return []

        # Sparse scoring: touch ONLY documents containing query terms
        scores = np.zeros(self.N, dtype=np.float64)

        for qt_idx in query_term_indices:
            if qt_idx not in self.inverted_index:
                continue

            doc_indices, tf_arr = self.inverted_index[qt_idx]
            idf_val = float(self.idf[qt_idx])

            # BM25 term formula for matching docs
            dl = self.doc_lengths[doc_indices]
            denom = tf_arr + k1 * (1.0 - b + b * dl / self.avgdl)
            term_scores = idf_val * (tf_arr * (k1 + 1.0)) / denom
            scores[doc_indices] += term_scores

        # Zero out scores for documents that fail source filter before top-k selection
        if filter_func:
            for doc_i in range(self.N):
                if scores[doc_i] > 0:
                    src = self.metadatas[doc_i].get("source_name", "")
                    if not filter_func(src):
                        scores[doc_i] = 0.0

        # Get top-k indices
        positive_mask = scores > 0
        if not np.any(positive_mask):
            return []

        if k >= self.N:
            top_indices = np.argsort(scores)[::-1]
        else:
            top_indices = np.argpartition(scores, -k)[-k:]
            top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        return [(int(i), float(scores[i])) for i in top_indices if scores[i] > 0]


def _get_bm25(persist_directory: str) -> BM25Retriever | None:
    """Get a cached BM25Retriever, rebuilding only when corpus changes."""
    jsonl_path = _corpus_path_jsonl(persist_directory)
    check_paths = [
        jsonl_path,
        _corpus_path_json(persist_directory),
        Path(persist_directory) / "chroma_db" / "bm25_corpus.jsonl",
        Path(persist_directory) / "chroma_db" / "bm25_corpus.json",
    ]

    current_mtime = 0.0
    for p in check_paths:
        if p.exists():
            current_mtime = max(current_mtime, p.stat().st_mtime)
            break

    if current_mtime == 0.0:
        return None

    if persist_directory in _bm25_cache:
        cached_mtime, cached_retriever = _bm25_cache[persist_directory]
        if cached_mtime == current_mtime:
            return cached_retriever

    corpus = _load_corpus(persist_directory)
    if not corpus or not corpus["texts"]:
        return None

    retriever = BM25Retriever(corpus["texts"], corpus["metadatas"])
    _bm25_cache[persist_directory] = (current_mtime, retriever)
    logger.info(
        "BM25 index built/rebuilt for %s: %d chunks", persist_directory, len(corpus["texts"])
    )
    return retriever


# ---------------------------------------------------------------------------
# Hybrid search with Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

import asyncio

async def ahybrid_search(
    query: str,
    vector_store,
    persist_directory: str,
    k: int = 6,
    filter_sources: list[str] | None = None,
) -> list[Document]:
    """Combine BM25 + semantic search concurrently using Reciprocal Rank Fusion.

    Args:
        query: Search query string.
        vector_store: QdrantVectorStore instance.
        persist_directory: Session persist directory.
        k: Top-k results to return.
        filter_sources: Optional list of source names (filenames or URLs) to filter by.
    """

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
            fetch_k = 100 if norm_filters else k * 2
            retriever = vector_store.as_retriever(search_kwargs={"k": fetch_k})
            docs = await retriever.ainvoke(query)
            if norm_filters:
                docs = [d for d in docs if _matches_filter(d.metadata.get("source_name", ""))]
            return docs[: k * 2]
        except Exception as exc:
            logger.warning("Semantic search failed: %s", exc)
            return []

    async def _search_bm25():
        try:
            bm25 = _get_bm25(persist_directory)
            if bm25 is not None:
                filter_func = _matches_filter if norm_filters else None
                hits = bm25.search(query, k=k * 4 if norm_filters else k * 2, filter_func=filter_func)
                return bm25, hits[: k * 2]
        except Exception as exc:
            logger.warning("BM25 search failed: %s", exc)
        return None, []

    semantic_task = asyncio.create_task(_search_semantic())
    bm25_task = asyncio.create_task(_search_bm25())

    semantic_docs, (bm25, bm25_hits) = await asyncio.gather(semantic_task, bm25_task)

    bm25_results = {}
    semantic_results = {}

    if bm25_hits:
        for rank, (idx, _score) in enumerate(bm25_hits):
            bm25_results[idx] = rank

    for rank, doc in enumerate(semantic_docs):
        key = doc.page_content[:200]
        semantic_results[key] = (rank, doc)

    # --- Reciprocal Rank Fusion ---
    rrf_scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}
    source_map: dict[str, str] = {}

    k_rrf = 60

    if bm25 is not None and bm25_results:
        corpus_texts = bm25.texts
        corpus_metas = bm25.metadatas
        for idx, rank in bm25_results.items():
            text = corpus_texts[idx]
            key = text[:200]
            rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k_rrf + rank + 1)
            meta = corpus_metas[idx]
            source_map[key] = meta.get("source_name", "unknown")
            doc_map[key] = Document(page_content=text, metadata=meta)

    for key, (rank, doc) in semantic_results.items():
        rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k_rrf + rank + 1)
        if key not in doc_map:
            doc_map[key] = doc
            source_map[key] = doc.metadata.get("source_name", "unknown")

    sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)
    results = [doc_map[k] for k in sorted_keys[:k] if k in doc_map]
    return results


# ---------------------------------------------------------------------------
# Document deduplication via file hashes
# ---------------------------------------------------------------------------

def _file_hashes_path(persist_directory: str) -> Path:
    return Path(persist_directory) / "processed_files.json"


def _load_file_hashes(persist_directory: str) -> dict[str, str]:
    """Load {filename: md5_hash} map from disk."""
    path = _file_hashes_path(persist_directory)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_file_hashes(persist_directory: str, hashes: dict[str, str]):
    """Persist the file hash map."""
    path = _file_hashes_path(persist_directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(hashes, ensure_ascii=False), encoding="utf-8")


def _compute_file_hash(file_bytes: bytes) -> str:
    """Compute MD5 hash of file content."""
    return hashlib.md5(file_bytes).hexdigest()


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

def _extract_doc_title(file_name: str, text: str) -> str:
    """Extract a title from the document content, falling back to filename."""
    # Try to find a heading in the first 500 chars
    for pattern in [r"^#\s+(.+)", r"^(.{10,80})\n[=\-]{3,}"]:
        m = re.search(pattern, text[:500], re.MULTILINE)
        if m:
            return m.group(1).strip()
    # Fallback: filename without extension
    return Path(file_name).stem


def load_documents(uploaded_files):
    """Load documents from uploaded Streamlit file objects based on file type."""
    all_documents = []
    for uploaded_file in uploaded_files:
        suffix = os.path.splitext(uploaded_file.name)[1].lower()
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.getbuffer())
                tmp_path = tmp.name

            if suffix == ".pdf":
                loader = PyPDFLoader(tmp_path)
            elif suffix == ".md":
                loader = UnstructuredMarkdownLoader(tmp_path)
            elif suffix == ".csv":
                loader = CSVLoader(tmp_path)
            elif suffix == ".docx":
                loader = Docx2txtLoader(tmp_path)
            elif suffix == ".txt":
                loader = TextLoader(tmp_path, autodetect_encoding=True)
            elif suffix == ".pptx":
                loader = UnstructuredPowerPointLoader(tmp_path)
            else:
                continue

            documents = loader.load()
            for doc in documents:
                doc.page_content = _sanitize_text(doc.page_content)
                doc.metadata["source_type"] = suffix.lstrip(".")
                doc.metadata["source_name"] = uploaded_file.name
            all_documents.extend(documents)
            logger.info("Loaded %d pages from %s", len(documents), uploaded_file.name)
        except Exception as exc:
            logger.error("Failed to load %s: %s", uploaded_file.name, exc)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    return all_documents





def load_url(url: str):
    """Scrape a web page and return LangChain documents."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        loader = WebBaseLoader(url, header_template=headers)
        documents = loader.load()
        for doc in documents:
            doc.page_content = _sanitize_text(doc.page_content)
            doc.metadata["source_type"] = "url"
            doc.metadata["source_name"] = url
        return documents
    except Exception as exc:
        logger.error("Failed to load URL %s: %s", url, exc)
        return []


# ---------------------------------------------------------------------------
# Chunk enrichment
# ---------------------------------------------------------------------------

def _enrich_chunks(chunks: list[Document], source_name: str = "") -> list[Document]:
    """Add rich metadata to chunks for better retrieval and attribution."""
    if not chunks:
        return chunks

    # Extract title from first chunk's content
    doc_title = _extract_doc_title(
        source_name or "unknown",
        chunks[0].page_content if chunks else "",
    )

    total = len(chunks)
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i
        chunk.metadata["total_chunks"] = total
        chunk.metadata["doc_title"] = doc_title

    return chunks


# ---------------------------------------------------------------------------
# Batch embedding helper
# ---------------------------------------------------------------------------

async def _batch_add_documents(
    vector_store,
    chunks: list[Document],
    batch_size: int = EMBEDDING_BATCH_SIZE,
    progress_callback=None,
):
    """Add documents to vector store in batches to avoid OOM on large sets."""
    total = len(chunks)
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch = chunks[start:end]
        await vector_store.aadd_documents(batch)
        if progress_callback:
            progress_callback(end / total, f"Embedded {end}/{total} chunks")
        logger.info("Embedded batch %d–%d of %d chunks", start + 1, end, total)


# ---------------------------------------------------------------------------
# Processing pipelines
# ---------------------------------------------------------------------------

async def process_uploaded_files(
    uploaded_files,
    existing_store=None,
    persist_directory="./qdrant_db",
    progress_callback=None,
    force: bool = False,
):
    """Process uploaded files into a vector store with embeddings.

    Args:
        uploaded_files: Streamlit file uploader objects.
        existing_store: Existing Qdrant vector store to append to.
        persist_directory: Where to persist the Qdrant DB and BM25 corpus.
        progress_callback: Optional callable(progress: float, label: str).
        force: If True, skip deduplication and re-process all files.
    """
    # --- Deduplication ---
    file_hashes = _load_file_hashes(persist_directory) if not force else {}
    files_to_process = []
    skipped = 0

    for uploaded_file in uploaded_files:
        file_bytes = uploaded_file.getbuffer()
        file_hash = _compute_file_hash(bytes(file_bytes))

        if not force and uploaded_file.name in file_hashes:
            if file_hashes[uploaded_file.name] == file_hash:
                logger.info("Skipping duplicate: %s", uploaded_file.name)
                skipped += 1
                continue

        files_to_process.append((uploaded_file, file_hash))

    if skipped:
        logger.info("Deduplication: skipped %d already-processed files", skipped)

    if not files_to_process:
        logger.warning("No new documents to process (all duplicates)")
        return existing_store, 0

    # --- Load documents ---
    if progress_callback:
        progress_callback(0.1, "Loading documents...")

    all_documents = load_documents([f for f, _ in files_to_process])
    if not all_documents:
        logger.warning("No documents loaded from uploaded files")
        return existing_store, 0

    # --- Split into chunks ---
    if progress_callback:
        progress_callback(0.3, "Splitting into chunks...")

    text_splitter = _get_text_splitter()
    chunks = text_splitter.split_documents(all_documents)
    chunks = [c for c in chunks if c.page_content.strip()]
    if not chunks:
        logger.warning("All chunks were empty after splitting")
        return existing_store, 0

    # --- Enrich metadata ---
    by_source: dict[str, list[Document]] = defaultdict(list)
    for chunk in chunks:
        src = chunk.metadata.get("source_name", "unknown")
        by_source[src].append(chunk)

    enriched_chunks = []
    for src_name, src_chunks in by_source.items():
        enriched_chunks.extend(_enrich_chunks(src_chunks, src_name))

    chunks = enriched_chunks
    logger.info("Indexed %d chunks from %d documents", len(chunks), len(all_documents))

    # --- Embed in batches ---
    if progress_callback:
        progress_callback(0.4, "Embedding chunks...")

    embeddings = _get_embeddings()
    if existing_store is None:
        existing_store = get_qdrant_vector_store(persist_directory, embedding=embeddings)

    await _batch_add_documents(
        existing_store, chunks,
        progress_callback=progress_callback,
    )
    _save_corpus(chunks, persist_directory, append=True)

    # --- Update file hashes ---
    for uploaded_file, file_hash in files_to_process:
        file_hashes[uploaded_file.name] = file_hash
    _save_file_hashes(persist_directory, file_hashes)

    if progress_callback:
        progress_callback(1.0, "Complete")

    return existing_store, len(chunks)


async def process_url(
    url: str,
    existing_store=None,
    persist_directory="./qdrant_db",
    progress_callback=None,
):
    """Scrape a URL and add its content to the vector store."""
    if progress_callback:
        progress_callback(0.1, f"Fetching and scraping web page: {url}")
    documents = load_url(url)
    if not documents:
        return existing_store, 0

    text_splitter = _get_text_splitter()
    chunks = text_splitter.split_documents(documents)
    chunks = [c for c in chunks if c.page_content.strip()]
    if not chunks:
        return existing_store, 0

    # Enrich metadata
    chunks = _enrich_chunks(chunks, url)

    embeddings = _get_embeddings()
    if existing_store is None:
        existing_store = get_qdrant_vector_store(persist_directory, embedding=embeddings)

    await _batch_add_documents(
        existing_store, chunks,
        progress_callback=progress_callback,
    )
    _save_corpus(chunks, persist_directory, append=True)
    return existing_store, len(chunks)
