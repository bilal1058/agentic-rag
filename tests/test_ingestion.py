"""Unit tests for core/ingestion.py IngestionEngine."""

from pathlib import Path
from langchain_core.documents import Document

from core.ingestion import (
    IngestionEngine,
    compute_file_hash,
    enrich_chunks,
    load_file_hashes,
    save_file_hashes,
    save_corpus,
)


def test_compute_file_hash():
    h1 = compute_file_hash(b"hello world")
    h2 = compute_file_hash(b"hello world")
    h3 = compute_file_hash(b"hello other")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64


def test_file_hashes_persistence(tmp_path: Path):
    hashes = {"doc1.pdf": "hash123", "notes.md": "hash456"}
    save_file_hashes(tmp_path, hashes)

    loaded = load_file_hashes(tmp_path)
    assert loaded == hashes


def test_enrich_chunks():
    chunks = [
        Document(page_content="Page 1 text", metadata={"page": 0}),
        Document(page_content="Page 2 text", metadata={"page": 1}),
        Document(page_content="Page 3 text", metadata={}),
    ]
    enriched = enrich_chunks(chunks, "quarterly_earnings_report.pdf")
    assert len(enriched) == 3

    assert enriched[0].metadata["doc_title"] == "quarterly earnings report"
    assert enriched[0].metadata["chunk_index"] == 0
    assert enriched[0].metadata["total_chunks"] == 3
    assert enriched[0].metadata["page_number"] == 1

    assert enriched[1].metadata["chunk_index"] == 1
    assert enriched[1].metadata["page_number"] == 2

    assert enriched[2].metadata["chunk_index"] == 2
    assert enriched[2].metadata["page_number"] is None


def test_save_corpus(tmp_path: Path):
    chunks = [
        Document(page_content="Content A", metadata={"source": "a"}),
        Document(page_content="Content B", metadata={"source": "b"}),
    ]
    save_corpus(chunks, tmp_path)

    corpus_file = tmp_path / "bm25_corpus.jsonl"
    assert corpus_file.exists()
    lines = corpus_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    assert "Content A" in lines[0]
    assert "Content B" in lines[1]
