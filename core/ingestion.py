"""Deep IngestionEngine Module for Multi-Format Documents and Web Scraping.

Encapsulates file parsing (PDF, DOCX, CSV, PPTX, TXT, MD), web page scraping,
chunk enrichment, hash-based deduplication, and corpus persistence behind a clean interface.
"""

import hashlib
import json
import logging
import os
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Sequence

from langchain_core.documents import Document

logger = logging.getLogger("ingestion")


class IngestionEngine:
    """Deep engine orchestrating multi-format document loading, deduplication, and chunking."""

    @staticmethod
    def compute_file_hash(content: bytes) -> str:
        """Compute SHA256 hex digest for document deduplication."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def hash_file_path(persist_directory: str | Path) -> Path:
        """Resolve the file hashes JSON path for a persistence directory."""
        return Path(persist_directory) / "file_hashes.json"

    @classmethod
    def load_file_hashes(cls, persist_directory: str | Path) -> dict[str, str]:
        """Load the dictionary of previously ingested file hashes."""
        path = cls.hash_file_path(persist_directory)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    @classmethod
    def save_file_hashes(cls, persist_directory: str | Path, hashes: dict[str, str]) -> None:
        """Persist file hashes to disk."""
        path = cls.hash_file_path(persist_directory)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(hashes, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to save file hashes to %s: %s", path, exc)

    @staticmethod
    def enrich_chunks(chunks: Sequence[Document], source_name: str) -> list[Document]:
        """Add metadata indexing, total chunks, document title, and 1-indexed page numbers."""
        total = len(chunks)
        doc_title = Path(source_name).stem.replace("_", " ").replace("-", " ")
        enriched = []
        for idx, chunk in enumerate(chunks):
            # Create a shallow copy of metadata to prevent mutating shared dicts
            meta = dict(chunk.metadata)
            meta["chunk_index"] = idx
            meta["total_chunks"] = total
            meta["doc_title"] = doc_title
            raw_page = meta.get("page")
            if isinstance(raw_page, int):
                meta["page_number"] = raw_page + 1
            elif raw_page:
                meta["page_number"] = raw_page
            else:
                meta["page_number"] = None
            enriched.append(Document(page_content=chunk.page_content, metadata=meta))
        return enriched

    @staticmethod
    def load_documents(uploaded_files) -> list[Document]:
        """Parse uploaded file buffers into langchain Document objects across supported formats."""
        documents: list[Document] = []
        for file in uploaded_files:
            name = getattr(file, "name", "document.txt")
            suffix = Path(name).suffix.lower()
            content = file.getbuffer() if hasattr(file, "getbuffer") else getattr(file, "content", b"")
            if isinstance(content, str):
                content = content.encode("utf-8")

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                if suffix == ".pdf":
                    from langchain_community.document_loaders import PyPDFLoader
                    docs = PyPDFLoader(tmp_path).load()
                elif suffix == ".docx":
                    from langchain_community.document_loaders import Docx2txtLoader
                    docs = Docx2txtLoader(tmp_path).load()
                elif suffix == ".csv":
                    from langchain_community.document_loaders import CSVLoader
                    docs = CSVLoader(tmp_path, encoding="utf-8").load()
                elif suffix == ".pptx":
                    from langchain_community.document_loaders import UnstructuredPowerPointLoader
                    docs = UnstructuredPowerPointLoader(tmp_path).load()
                else:
                    from langchain_community.document_loaders import TextLoader
                    docs = TextLoader(tmp_path, encoding="utf-8").load()

                for doc in docs:
                    doc.metadata["source_name"] = name
                    doc.metadata["source_type"] = suffix.lstrip(".")
                documents.extend(docs)
            except Exception as exc:
                logger.warning("Failed to parse %s: %s", name, exc)
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
        return documents

    @staticmethod
    def load_url(url: str) -> list[Document]:
        """Scrape a web page into Document objects."""
        try:
            from langchain_community.document_loaders import WebBaseLoader
            loader = WebBaseLoader(url)
            docs = loader.load()
            for doc in docs:
                doc.metadata["source_name"] = url
                doc.metadata["source_type"] = "url"
            return docs
        except Exception as exc:
            logger.warning("Failed to scrape URL %s: %s", url, exc)
            return []

    @staticmethod
    def save_corpus(chunks: Sequence[Document], persist_directory: str | Path, append: bool = False) -> None:
        """Save chunk text and metadata to a jsonl file for BM25 sparse indexing."""
        corpus_file = Path(persist_directory) / "bm25_corpus.jsonl"
        corpus_file.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(corpus_file, mode, encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps({"text": chunk.page_content, "metadata": chunk.metadata}, ensure_ascii=False) + "\n")

    @classmethod
    async def batch_add_documents(
        cls,
        vector_store,
        chunks: list[Document],
        batch_size: int = 50,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> None:
        """Asynchronously batch-add documents to a vector store with progress reporting."""
        total = len(chunks)
        for i in range(0, total, batch_size):
            batch = chunks[i: i + batch_size]
            await vector_store.aadd_documents(batch)
            if progress_callback:
                progress = min(0.4 + (i + len(batch)) / total * 0.5, 0.9)
                progress_callback(progress, f"Indexed {min(i + len(batch), total)}/{total} chunks")

    @classmethod
    async def ingest_files(
        cls,
        uploaded_files: list,
        existing_store=None,
        persist_directory: str | Path = "./qdrant_db",
        progress_callback: Callable[[float, str], None] | None = None,
        force: bool = False,
        embeddings=None,
        vector_store_factory=None,
        text_splitter=None,
    ) -> tuple[Any, int]:
        """Ingest a batch of uploaded files into vector store and BM25 corpus."""
        persist_dir_str = str(persist_directory)
        file_hashes = cls.load_file_hashes(persist_dir_str) if not force else {}
        files_to_process = []
        skipped = 0

        for uploaded_file in uploaded_files:
            file_bytes = uploaded_file.getbuffer() if hasattr(uploaded_file, "getbuffer") else getattr(uploaded_file, "content", b"")
            if isinstance(file_bytes, str):
                file_bytes = file_bytes.encode("utf-8")
            file_hash = cls.compute_file_hash(bytes(file_bytes))
            file_name = getattr(uploaded_file, "name", "file")
            if not force and file_name in file_hashes:
                if file_hashes[file_name] == file_hash:
                    skipped += 1
                    continue
            files_to_process.append((uploaded_file, file_hash))

        if not files_to_process:
            logger.info("No new documents to process (all duplicates)")
            if existing_store is None and vector_store_factory:
                existing_store = vector_store_factory(persist_dir_str, embedding=embeddings)
            return existing_store, 0

        if progress_callback:
            progress_callback(0.1, "Loading documents...")

        all_documents = cls.load_documents([f for f, _ in files_to_process])
        if not all_documents:
            return existing_store, 0

        if progress_callback:
            progress_callback(0.3, "Splitting into chunks...")

        if text_splitter is None:
            from core.rag import _get_text_splitter
            text_splitter = _get_text_splitter()

        chunks = text_splitter.split_documents(all_documents)
        chunks = [c for c in chunks if c.page_content.strip()]
        if not chunks:
            return existing_store, 0

        by_source: dict[str, list[Document]] = defaultdict(list)
        for chunk in chunks:
            by_source[chunk.metadata.get("source_name", "unknown")].append(chunk)

        enriched_chunks = []
        for src_name, src_chunks in by_source.items():
            enriched_chunks.extend(cls.enrich_chunks(src_chunks, src_name))
        chunks = enriched_chunks

        if progress_callback:
            progress_callback(0.4, "Embedding chunks...")

        if existing_store is None:
            if vector_store_factory is None:
                from core.rag import get_qdrant_vector_store, _get_embeddings
                embeddings = embeddings or _get_embeddings()
                existing_store = get_qdrant_vector_store(persist_dir_str, embedding=embeddings)
            else:
                existing_store = vector_store_factory(persist_dir_str, embedding=embeddings)

        await cls.batch_add_documents(existing_store, chunks, progress_callback=progress_callback)
        cls.save_corpus(chunks, persist_dir_str, append=True)

        for uploaded_file, file_hash in files_to_process:
            file_name = getattr(uploaded_file, "name", "file")
            file_hashes[file_name] = file_hash
        cls.save_file_hashes(persist_dir_str, file_hashes)

        if progress_callback:
            progress_callback(1.0, "Complete")

        return existing_store, len(chunks)

    @classmethod
    async def ingest_url(
        cls,
        url: str,
        existing_store=None,
        persist_directory: str | Path = "./qdrant_db",
        progress_callback: Callable[[float, str], None] | None = None,
        embeddings=None,
        vector_store_factory=None,
        text_splitter=None,
    ) -> tuple[Any, int]:
        """Ingest a web URL into vector store and BM25 corpus."""
        persist_dir_str = str(persist_directory)
        if progress_callback:
            progress_callback(0.1, f"Fetching and scraping web page: {url}")
        documents = cls.load_url(url)
        if not documents:
            return existing_store, 0

        if text_splitter is None:
            from core.rag import _get_text_splitter
            text_splitter = _get_text_splitter()

        chunks = text_splitter.split_documents(documents)
        chunks = [c for c in chunks if c.page_content.strip()]
        if not chunks:
            return existing_store, 0

        chunks = cls.enrich_chunks(chunks, url)
        if existing_store is None:
            if vector_store_factory is None:
                from core.rag import get_qdrant_vector_store, _get_embeddings
                embeddings = embeddings or _get_embeddings()
                existing_store = get_qdrant_vector_store(persist_dir_str, embedding=embeddings)
            else:
                existing_store = vector_store_factory(persist_dir_str, embedding=embeddings)

        await cls.batch_add_documents(existing_store, chunks, progress_callback=progress_callback)
        cls.save_corpus(chunks, persist_dir_str, append=True)
        return existing_store, len(chunks)


# Convenience aliases for backward compatibility
compute_file_hash = IngestionEngine.compute_file_hash
load_file_hashes = IngestionEngine.load_file_hashes
save_file_hashes = IngestionEngine.save_file_hashes
enrich_chunks = IngestionEngine.enrich_chunks
load_documents = IngestionEngine.load_documents
load_url = IngestionEngine.load_url
save_corpus = IngestionEngine.save_corpus
ingest_files = IngestionEngine.ingest_files
ingest_url = IngestionEngine.ingest_url
