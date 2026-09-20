"""Deep EvaluationEngine Module for RAG Telemetry and RAGAS Benchmarking.

Encapsulates dataset construction, judge LLM initialization, embeddings adaptation,
faithfulness/relevance metrics, and observer progress callbacks behind a single seam.
"""

import logging
import os
from typing import Any, Callable, Optional

import numpy as np

logger = logging.getLogger("evaluation")


class EvaluationEngine:
    """Deep engine orchestrating RAGAS evaluation metrics for RAG generation quality."""

    @classmethod
    def evaluate_response(
        cls,
        question: str,
        answer: str,
        context: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        llm: Any = None,
        embeddings: Any = None,
    ) -> Optional[dict[str, float]]:
        """Run Ragas evaluation using a judge LLM and embeddings wrapper."""
        if not question or not answer or not context:
            logger.warning("RAGAS evaluation skipped: question, answer, or context missing.")
            return None

        try:
            from datasets import Dataset
            from ragas import evaluate
            from ragas.llms import LangchainLLMWrapper
            from ragas.metrics import answer_relevancy, context_precision, faithfulness

            if progress_callback:
                progress_callback(0.1, "Preparing evaluation dataset...")

            dataset = Dataset.from_dict({
                "question": [question],
                "answer": [answer],
                "contexts": [[context]],
                "ground_truth": [answer],
            })

            eval_llm = llm
            if eval_llm is None:
                from langchain_groq import ChatGroq
                from core.rag import get_active_model_name, _get_fallback_llm

                api_key = os.environ.get("GROQ_API_KEY")
                if api_key:
                    eval_llm = ChatGroq(
                        model=get_active_model_name(),
                        api_key=api_key,
                        max_tokens=500,
                        temperature=0.0,
                    )
                else:
                    eval_llm = _get_fallback_llm()

            if not eval_llm:
                logger.warning("No LLM available for RAGAS evaluation.")
                return None

            if progress_callback:
                progress_callback(0.3, "Configuring metric estimators...")

            llm_wrapper = LangchainLLMWrapper(eval_llm)

            embeddings_wrapper = embeddings
            if embeddings_wrapper is None:
                from core.rag import _get_embeddings
                embeddings_wrapper = _get_embeddings()

            faithfulness.llm = llm_wrapper
            answer_relevancy.llm = llm_wrapper
            answer_relevancy.embeddings = embeddings_wrapper
            context_precision.llm = llm_wrapper

            if progress_callback:
                progress_callback(0.6, "Computing faithfulness & relevance...")

            result = evaluate(
                dataset,
                metrics=[faithfulness, answer_relevancy, context_precision],
                llm=llm_wrapper,
                embeddings=embeddings_wrapper,
            )

            if progress_callback:
                progress_callback(1.0, "Evaluation complete")

            return {k: float(v) for k, v in result.items() if not np.isnan(v)}
        except Exception as exc:
            logger.warning("RAGAS evaluation failed: %s", exc)
            return None


def evaluate_ragas(question: str, answer: str, context: str, progress_callback=None) -> Optional[dict[str, float]]:
    """Convenience wrapper delegating to EvaluationEngine."""
    return EvaluationEngine.evaluate_response(question, answer, context, progress_callback=progress_callback)
