"""Unit tests for core/evaluation.py EvaluationEngine."""

from unittest.mock import MagicMock, patch
from core.evaluation import EvaluationEngine, evaluate_ragas


def test_evaluation_engine_empty_inputs():
    assert EvaluationEngine.evaluate_response("", "answer", "context") is None
    assert EvaluationEngine.evaluate_response("question", "", "context") is None
    assert EvaluationEngine.evaluate_response("question", "answer", "") is None
    assert evaluate_ragas("", "", "") is None


def test_evaluation_engine_mocked_run():
    mock_llm = MagicMock()
    mock_embeddings = MagicMock()

    mock_result = {"faithfulness": 0.95, "answer_relevancy": 0.88}

    with patch("ragas.evaluate", return_value=mock_result), \
         patch("ragas.llms.LangchainLLMWrapper"), \
         patch("datasets.Dataset.from_dict"):
        scores = EvaluationEngine.evaluate_response(
            question="What is Agentic RAG?",
            answer="Agentic RAG uses multi-hop autonomous agents to retrieve and reason.",
            context="Agentic RAG combines retrieval augmented generation with agent loops.",
            llm=mock_llm,
            embeddings=mock_embeddings,
        )
        assert scores == mock_result
        assert scores["faithfulness"] == 0.95
