"""RAGAS evaluation script for the RAG chatbot.

Measures faithfulness, answer relevancy, and context precision of agent
answers against the currently indexed documents.

Usage:
    python evaluate_rag.py                          # newest session store, sample questions
    python evaluate_rag.py --db ./chroma_db         # explicit vector store directory
    python evaluate_rag.py -q "What is X?" -q "..." # custom questions
    python evaluate_rag.py --questions questions.txt

Requires GROQ_API_KEY (and optionally OPENROUTER_API_KEY) in .env.
"""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("evaluate_rag")

ROOT = Path(__file__).parent

DEFAULT_QUESTIONS = [
    "Summarize the main points of the document.",
    "What are the key topics covered in the document?",
]


def find_vector_store_dir(explicit: str | None) -> Path | None:
    """Return the directory containing a persisted Qdrant store."""
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None

    candidates = []
    for db_name in ["qdrant_db", "chroma_db"]:
        root_db = ROOT / db_name
        if root_db.exists():
            candidates.append(root_db)
        sessions_dir = ROOT / "sessions"
        if sessions_dir.exists():
            candidates.extend(d / db_name for d in sessions_dir.iterdir() if (d / db_name).exists())

    if not candidates:
        return None
    # Newest first
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_vector_store(db_dir: Path):
    from rag_engine import get_qdrant_vector_store

    return get_qdrant_vector_store(str(db_dir))


def answer_question(question: str, vector_store, db_dir: Path) -> tuple[str, str]:
    """Retrieve context and generate an answer. Returns (answer, context)."""
    import os
    import asyncio
    from langchain_groq import ChatGroq
    from langchain_core.messages import SystemMessage, HumanMessage
    from rag_engine import ahybrid_search
    from rag_agent import _invoke_llm

    docs = asyncio.run(ahybrid_search(question, vector_store, str(db_dir), k=6))
    context = "\n\n".join(d.page_content for d in docs) if docs else ""
    if not context:
        return "", ""

    llm = ChatGroq(
        model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.environ.get("GROQ_API_KEY"),
        temperature=0.0,
    )
    prompt = (
        "Answer the user's question based EXCLUSIVELY on the context below. "
        "If the context does not contain the answer, say so.\n\n"
        f"=== CONTEXT ===\n{context}\n==============="
    )
    response = asyncio.run(_invoke_llm(llm, [SystemMessage(content=prompt), HumanMessage(content=question)]))
    return getattr(response, "content", ""), context


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAG answers with RAGAS.")
    parser.add_argument("--db", help="Path to a Chroma persist directory")
    parser.add_argument("-q", "--question", action="append", dest="questions",
                        help="Question to evaluate (repeatable)")
    parser.add_argument("--questions", dest="questions_file",
                        help="Path to a text file with one question per line")
    args = parser.parse_args()

    db_dir = find_vector_store_dir(args.db)
    if db_dir is None:
        print("No vector store found. Upload documents in the app first, "
              "or pass --db <path-to-chroma_db>.")
        return 1
    print(f"Using vector store: {db_dir}")

    questions = list(args.questions or [])
    if args.questions_file:
        lines = Path(args.questions_file).read_text(encoding="utf-8").splitlines()
        questions.extend(l.strip() for l in lines if l.strip())
    if not questions:
        questions = DEFAULT_QUESTIONS
        print("No questions provided — using sample questions.")

    vector_store = load_vector_store(db_dir)
    from rag_agent import evaluate_ragas

    all_scores = []
    for i, question in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}] {question}")
        answer, context = answer_question(question, vector_store, db_dir)
        if not answer:
            print("  ! No context retrieved — skipping.")
            continue
        print(f"  Answer: {answer[:120]}{'...' if len(answer) > 120 else ''}")

        scores = evaluate_ragas(
            question, answer, context,
            progress_callback=lambda p, label: print(f"  {label} ({p:.0%})"),
        )
        if scores is None:
            print("  ! RAGAS evaluation failed for this question.")
            continue
        all_scores.append(scores)
        for metric, value in scores.items():
            print(f"  {metric:20s} {value:.3f}")

    if not all_scores:
        print("\nNo questions were successfully evaluated.")
        return 1

    print("\n" + "=" * 40)
    print(f"Averages over {len(all_scores)} question(s):")
    for metric in all_scores[0]:
        avg = sum(s[metric] for s in all_scores) / len(all_scores)
        print(f"  {metric:20s} {avg:.3f}")
    print("=" * 40)
    return 0


if __name__ == "__main__":
    sys.exit(main())
