import pytest
from langchain_core.documents import Document
from core.rag import _enrich_chunks, extract_result_metadata


def test_enrich_chunks_preserves_page_numbers():
    chunks = [
        Document(page_content="Bilal's experience in LangGraph.", metadata={"page": 0, "source_type": "pdf"}),
        Document(page_content="Bilal's project deployments.", metadata={"page": 1, "source_type": "pdf"}),
    ]
    enriched = _enrich_chunks(chunks, "Muhammad_Bilal_Resume.pdf")
    assert len(enriched) == 2
    assert enriched[0].metadata["page_number"] == 1
    assert enriched[1].metadata["page_number"] == 2
    assert enriched[0].metadata["doc_title"] == "Muhammad Bilal Resume"


def test_extract_result_metadata_parses_page_citations():
    context = (
        "[Document 1: Muhammad_Bilal_Resume.pdf | Page 1]\nBilal is an AI Engineer with ML skills.\n\n"
        "[Document 2: Arham_Tahir_Resume.pdf | Page 2]\nArham is a Software Engineer co-founder."
    )
    result = {
        "messages": [{"role": "assistant", "content": "Comparison of Bilal and Arham."}],
        "agent_path": "retrieval",
        "context_used": context,
    }
    answer, metadata = extract_result_metadata(result)
    assert answer == "Comparison of Bilal and Arham."
    assert metadata["chunks"] == 2
    sources = metadata["sources"]
    assert len(sources) == 2
    assert sources[0]["name"] == "Muhammad_Bilal_Resume.pdf"
    assert sources[0]["page"] == "1"
    assert sources[1]["name"] == "Arham_Tahir_Resume.pdf"
    assert sources[1]["page"] == "2"


def test_extract_result_metadata_deduplicates_sources():
    context = (
        "[Document 1: Policy.pdf | Page 3]\nSection 1 rules.\n\n"
        "[Document 2: Policy.pdf | Page 3]\nSection 2 rules."
    )
    result = {
        "messages": [{"role": "assistant", "content": "Rules summary."}],
        "agent_path": "retrieval",
        "context_used": context,
    }
    _, metadata = extract_result_metadata(result)
    assert len(metadata["sources"]) == 1
    assert metadata["sources"][0]["page"] == "3"
