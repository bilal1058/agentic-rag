import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.documents import Document
from core.rag import HybridRetriever, get_hybrid_retriever


@pytest.mark.asyncio
async def test_hybrid_retriever_search_and_format():
    mock_vs = MagicMock()
    # Pass cross_encoder=False to avoid loading heavy HF model in unit test
    retriever = get_hybrid_retriever(mock_vs, session_dir="", cross_encoder=False)
    retriever.ahybrid_search = AsyncMock(return_value=[
        Document(page_content="RAG pipelines use retrieval.", metadata={"source_name": "ai.pdf", "page_number": 3}),
        Document(page_content="Vector stores index embeddings.", metadata={"source_name": "db.pdf", "page_number": 2}),
    ])

    formatted = await retriever.search_and_format("test query")
    assert "[Document 1: ai.pdf | Page 3]" in formatted
    assert "RAG pipelines use retrieval." in formatted
    assert "[Document 2: db.pdf | Page 2]" in formatted


@pytest.mark.asyncio
async def test_hybrid_retriever_empty_results():
    mock_vs = MagicMock()
    retriever = HybridRetriever(mock_vs, session_dir="", cross_encoder=False)
    retriever.ahybrid_search = AsyncMock(return_value=[])

    formatted = await retriever.search_and_format("unknown")
    assert "No relevant documents found" in formatted
