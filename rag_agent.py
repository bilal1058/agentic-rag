import os
import re
import logging
from pathlib import Path
from typing import TypedDict, Optional, Annotated

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import (
    SystemMessage, HumanMessage, AIMessage, BaseMessage, ToolMessage,
)
from langgraph.graph import StateGraph, START, END
from langgraph.graph import add_messages
from nemoguardrails import RailsConfig, LLMRails

load_dotenv()

os.environ.setdefault("OPENAI_API_KEY", os.environ.get("GROQ_API_KEY", ""))

logger = logging.getLogger(__name__)


def _is_rate_limit_error(exc):
    """Check if an exception is a rate limit (429) error."""
    exc_str = str(exc)
    return any(kw in exc_str for kw in ("429", "rate_limit", "Rate limit", "rate limit reached"))


def _retry_after_seconds(exc, default: float) -> float:
    """Extract Groq's suggested wait (e.g. 'try again in 6.6s') if present."""
    m = re.search(r"try again in ([\d.]+)s", str(exc))
    if m:
        try:
            return min(float(m.group(1)) + 0.5, 30.0)
        except ValueError:
            pass
    return default


async def _invoke_with_backoff(llm, messages, tools=None, max_retries=3):
    """Call an LLM, retrying 429s with exponential backoff + jitter.

    Raises the last exception once retries are exhausted (caller then falls
    back to the secondary LLM)."""
    import asyncio
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
            if _is_rate_limit_error(e):
                fallback = _get_fallback_llm()
                if fallback:
                    logger.warning("Groq rate limit (429) hit. Escalating immediately to OpenRouter fallback LLM.")
                    raise
                if attempt < max_retries - 1:
                    wait = min(_retry_after_seconds(e, delay), 2.0) + random.uniform(0, 0.2)
                    logger.warning(
                        "Groq 429 — backing off %.1fs (attempt %d/%d)",
                        wait, attempt + 1, max_retries,
                    )
                    await asyncio.sleep(wait)
                    delay *= 2
                    continue
            raise
    raise last_exc


_fallback_llm = None


def _get_fallback_llm(model_override: str | None = None):
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        dotenv_path = Path(__file__).parent / ".env"
        if dotenv_path.exists():
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=dotenv_path)
            api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None
    from langchain_openai import ChatOpenAI
    model_name = model_override or os.environ.get("OPENROUTER_MODEL", "nvidia/nemotron-nano-9b-v2:free")
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=0.0,
        max_tokens=1024,
        request_timeout=10.0,
    )


async def _invoke_llm(primary_llm, messages, tools=None):
    """Invoke LLM with 429 backoff, then automatic fallback on failure."""
    try:
        return await _invoke_with_backoff(primary_llm, messages, tools=tools)
    except Exception as e:
        logger.warning("Primary LLM failed or rate-limited (%s): %s. Switching to OpenRouter fallback.", type(e).__name__, e)
        fallback_models = ["nvidia/nemotron-nano-9b-v2:free", "google/gemma-4-26b-a4b-it:free"]
        for fallback_model in fallback_models:
            fallback = _get_fallback_llm(model_override=fallback_model)
            if fallback:
                try:
                    if tools:
                        return await fallback.bind_tools(tools).ainvoke(messages)
                    return await fallback.ainvoke(messages)
                except Exception as fallback_err:
                    logger.warning("Fallback model %s failed: %s", fallback_model, fallback_err)
                    if tools:
                        try:
                            return await fallback.ainvoke(messages)
                        except Exception:
                            pass
        return AIMessage(content="I am currently experiencing high API rate limits. Please try asking your question again in a moment.")

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_NO_DOCS = (
    "You are a helpful assistant. "
    "No documents have been uploaded yet. Answer all questions from your "
    "own knowledge. If the user asks about a specific document, let them "
    "know they need to upload files first. "
    "NEVER say 'sorry', 'I apologize', or any apologetic phrases. "
    "Always respond directly and confidently."
)



# ---------------------------------------------------------------------------
# Cached heavy resources (loaded once, reused across requests)
# ---------------------------------------------------------------------------
_cross_encoder_instance = None
_rails_instance = None


def _get_cross_encoder():
    global _cross_encoder_instance
    if _cross_encoder_instance is None:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder_instance = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2")
            logger.info("Cross-encoder reranker loaded")
        except Exception:
            logger.warning("Cross-encoder not available")
            _cross_encoder_instance = False
    return _cross_encoder_instance if _cross_encoder_instance is not False else None


def _get_rails():
    global _rails_instance
    if _rails_instance is None:
        try:
            config_path = os.path.join(os.path.dirname(__file__), "guardrails_config")
            config = RailsConfig.from_path(config_path)
            _rails_instance = LLMRails(config)
            logger.info("NeMo Guardrails loaded")
        except Exception as exc:
            logger.warning("Failed to load Guardrails: %s", exc)
            _rails_instance = False
    return _rails_instance if _rails_instance is not False else None


# ---------------------------------------------------------------------------
# Agent State
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
    agent_path: str
    context_used: str


def _to_langchain_messages(messages, max_turns: int = 6):
    """Convert dict or BaseMessage list to LangChain message objects, capping history to recent turns."""
    recent_messages = messages[-max_turns:] if len(messages) > max_turns else messages
    converted = []
    for msg in recent_messages:
        if isinstance(msg, BaseMessage):
            converted.append(msg)
        elif isinstance(msg, dict):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "assistant" and len(content) > 600:
                content = content[:500] + "\n... [prior response condensed for speed]"
            if role == "system":
                converted.append(SystemMessage(content=content))
            elif role == "assistant":
                converted.append(AIMessage(content=content))
            else:
                converted.append(HumanMessage(content=content))
        else:
            converted.append(HumanMessage(content=str(msg)))
    return converted


# ---------------------------------------------------------------------------
# Retriever tool with hybrid search + reranking
# ---------------------------------------------------------------------------

def create_hybrid_retriever_tool(vector_store, session_dir: str = "", filter_sources: list[str] | None = None):
    """Creates a hybrid retriever tool combining BM25 + semantic search with reranking."""
    _cross_encoder = _get_cross_encoder()

    @tool
    async def search_documents(query: str) -> str:
        """Search uploaded documents for specific information. Use this tool whenever the user asks about their uploaded files, documents, URLs, or says 'summarize', 'explain', 'what does it say', etc.

        Args:
            query: The search query to find relevant document content.
        """
        from rag_engine import ahybrid_search

        docs = await ahybrid_search(query, vector_store, session_dir, k=10, filter_sources=filter_sources)
        if not docs and filter_sources:
            logger.info("Targeted retrieval returned 0 docs for %s; trying broader query on target file", filter_sources)
            docs = await ahybrid_search("overview summary technologies details project content", vector_store, session_dir, k=10, filter_sources=filter_sources)

        if not docs:
            return "No relevant documents found. The document content could not be retrieved."

        if _cross_encoder is not None and len(docs) > 1:
            pairs = [(query, doc.page_content) for doc in docs]
            import asyncio
            scores = await asyncio.to_thread(_cross_encoder.predict, pairs)
            scored_docs = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
            docs = [doc for _, doc in scored_docs[:6]]
        else:
            docs = docs[:6]

        parts = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source_name", "unknown")
            page = doc.metadata.get("page")
            if isinstance(page, int):
                page = page + 1  # PyPDFLoader pages are 0-based
            page_str = f" (page {page})" if page not in (None, "") else ""
            parts.append(f"[Source {i}: {source}{page_str}]\n{doc.page_content}")

        return "\n\n".join(parts)

    return search_documents


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------

async def check_input(state: AgentState) -> dict:
    last_message = state["messages"][-1]
    user_text = getattr(last_message, "content", str(last_message))

    _harmless_patterns = [
        "summarize", "explain", "what", "how", "who", "when", "where",
        "tell me", "describe", "list", "define", "compare", "analyze",
        "hello", "hi", "hey", "thanks", "thank you", "yes", "no",
        "i am", "i'm", "im ", "fine", "good", "ok", "okay", "cool", "great",
        "nice", "how are you", "what's up", "doing well",
    ]
    _suspicious_keywords = [
        "ignore", "disregard", "forget", "override", "bypass", "jailbreak",
        "system prompt", "your instructions", "your prompt", "your rules",
        "instead say", "pretend", "act as", "roleplay", "role-play",
        "you are now", "new instructions", "developer mode", "dan mode",
        "reveal", "repeat the words", "repeat everything", "print your",
        "output your", "api key", "password", "secret",
    ]
    lower_text = user_text.lower()
    is_harmless = any(p in lower_text for p in _harmless_patterns) or len(user_text) < 150
    is_suspicious = any(kw in lower_text for kw in _suspicious_keywords)
    if is_harmless and not is_suspicious and len(user_text) < 300:
        return {"blocked_reason": None}

    rails = _get_rails()
    if rails is not None:
        try:
            import asyncio
            # Offload synchronous NeMo Guardrails generation to thread pool
            response = await asyncio.to_thread(
                rails.generate,
                messages=[{"role": "user", "content": user_text}],
            )
            blocked_phrases = [
                "cannot process", "not allowed", "i'm sorry",
                "i cannot", "i can't", "not able to",
            ]
            is_blocked = any(p in response["content"].lower() for p in blocked_phrases)
            if is_blocked:
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
            "messages": [AIMessage(
                content=f"Reached the maximum of {max_calls} reasoning steps. Here is what I found so far."
            )],
        }
    return {"model_call_count": current_count}


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def _update_streamlit_state(key, value):
    try:
        import streamlit as st
        if hasattr(st, "session_state"):
            st.session_state[key] = value
    except Exception:
        pass


def build_agent_graph(vector_store, session_dir: str = ""):
    """Build the agentic RAG graph with forced retrieval when docs exist."""
    has_documents = vector_store is not None
    search_tool = None

    if has_documents:
        search_tool = create_hybrid_retriever_tool(vector_store, session_dir)

    llm = ChatGroq(
        model=os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
        api_key=os.environ.get("GROQ_API_KEY"),
        temperature=0.0,
        request_timeout=8.0,
        max_tokens=1024,
    )

    # ---- Nodes ----

    async def agent_decision(state: AgentState):
        calls = state.get("model_call_count", 0) + 1
        _update_streamlit_state("last_model_calls", calls)

        # Check for casual chat / greetings
        user_text = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage) and msg.content:
                user_text = msg.content
                break
            elif isinstance(msg, dict) and msg.get("role") == "user" and msg.get("content"):
                user_text = msg["content"]
                break

        clean_user = user_text.strip().lower().rstrip(".!?,")
        casual_phrases = {
            "hi", "hello", "hey", "i am fine", "i'm fine", "im fine", "i am good", "i'm good", "im good",
            "fine", "good", "ok", "okay", "cool", "great", "thanks", "thank you", "how are you",
            "what's up", "doing well", "nice to meet you", "good morning", "good evening", "good afternoon",
            "who are you", "what can you do", "help",
        }
        is_casual = clean_user in casual_phrases or (
            len(clean_user) < 25 and any(p in clean_user for p in ["hi", "hello", "hey", "fine", "good", "how are you", "thanks"])
            and not any(kw in clean_user for kw in ["pdf", "doc", "file", "url", "summary", "explain", "what is", "how to", "search", "project", "code"])
        )

        if is_casual:
            system_msg = SystemMessage(content=(
                "You are a friendly AI assistant. Answer the user's casual phrase concisely, warmly, and directly. "
                "Do NOT mention any documents or search results. NEVER say 'sorry' or 'I apologize'."
            ))
            # Send only system message + current user greeting to eliminate token buildup and keep response ultra-fast (<0.5s)
            messages = [system_msg, HumanMessage(content=user_text)]
            try:
                response = await _invoke_llm(llm, messages)
                return {"messages": [response], "agent_path": "direct"}
            except Exception as exc:
                logger.error("Casual agent response failed: %s", exc)
                return {
                    "messages": [AIMessage(content="Hello! How can I help you today?")],
                    "agent_path": "direct",
                }

        if has_documents:
            # Documents are indexed in the session — route directly to retrieval
            # to avoid Groq's tool_use_failed 400 error and eliminate extra LLM call overhead.
            return {"agent_path": "retrieval"}

        system_msg = SystemMessage(content=SYSTEM_PROMPT_NO_DOCS)
        messages = [system_msg] + _to_langchain_messages(state["messages"])

        try:
            response = await _invoke_llm(llm, messages)
            return {"messages": [response], "agent_path": "direct"}
        except Exception as exc:
            logger.error("Agent decision failed: %s", exc)
            raise

    async def _rewrite_query_with_history(query: str, messages) -> str:
        """Make a follow-up question standalone by resolving pronouns/references
        against the chat history (e.g. "what about its pricing?")."""
        history = []
        for msg in messages:
            if isinstance(msg, HumanMessage) and msg.content:
                history.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content:
                history.append(f"Assistant: {msg.content[:300]}")
        # First question of the conversation needs no rewriting
        if sum(1 for h in history if h.startswith("User:")) < 2:
            return query
        try:
            response = await _invoke_llm(llm, [
                SystemMessage(content=(
                    "Rewrite the user's latest question as a standalone search query for document retrieval. "
                    "RULES:\n"
                    "1. Resolve vague pronouns (it, its, that, these) against history ONLY if the question clearly continues the same topic.\n"
                    "2. If the question mentions 'this project', 'this file', 'this pdf', or 'the project', do NOT inject specific names/topics from previous web links or old conversations into the query.\n"
                    "3. Keep the query focused and neutral so it matches newly uploaded documents. Return ONLY the rewritten query."
                )),
                HumanMessage(content=(
                    "Conversation so far:\n" + "\n".join(history[-6:-1])
                    + f"\n\nLatest question: {query}"
                )),
            ])
            rewritten = getattr(response, "content", "").strip().strip('"')
            if 0 < len(rewritten) < 300:
                if rewritten != query:
                    logger.info("Query rewritten for retrieval: %r -> %r", query, rewritten)
                return rewritten
        except Exception as exc:
            logger.warning("Query rewrite failed, using original: %s", exc)
        return query

    async def force_retrieve(state: AgentState):
        """Execute the LLM's tool call and return context for respond node."""
        if not has_documents:
            return {"messages": [], "context_used": "", "agent_path": "direct"}

        # Check if the last AI message has a tool call to execute
        last_ai_msg = None
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage):
                last_ai_msg = msg
                break

        tool_call_id = None
        search_query = None
        if last_ai_msg and hasattr(last_ai_msg, "tool_calls") and last_ai_msg.tool_calls:
            tc = last_ai_msg.tool_calls[0]
            tool_call_id = tc.get("id", "tool_call")
            search_query = tc.get("args", {}).get("query", "")

        # Fallback: use last user message as query, made standalone via history
        if not search_query:
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

        # Determine target sources for this turn based on state messages and query
        all_known_sources = list(state.get("file_names") or []) + list(state.get("url_names") or [])
        target_sources = None

        search_query_lower = search_query.lower()
        is_explicit_compare = any(kw in search_query_lower for kw in ["compare", "all documents", "all files", "both documents", "both files"])

        if not is_explicit_compare:
            # 1. Check if the latest user message has attached files/URLs
            latest_user_files = []
            for msg in reversed(state["messages"]):
                files_list = []
                if isinstance(msg, dict) and msg.get("role") == "user":
                    files_list = msg.get("files", [])
                elif isinstance(msg, HumanMessage) and hasattr(msg, "additional_kwargs"):
                    files_list = msg.additional_kwargs.get("files", [])

                if files_list:
                    latest_user_files = [
                        f.get("name") for f in files_list
                        if isinstance(f, dict) and f.get("name")
                    ]
                    break

            if latest_user_files:
                target_sources = latest_user_files
            else:
                # 2. Check if user query explicitly names a specific file or URL
                mentioned_sources = [
                    s for s in all_known_sources
                    if Path(s).name.lower() in search_query_lower or s.lower() in search_query_lower
                ]
                if mentioned_sources:
                    target_sources = mentioned_sources
                else:
                    # 3. Fallback: check most recent user message that had attachments
                    for msg in reversed(state["messages"]):
                        msg_files = []
                        if isinstance(msg, dict) and msg.get("role") == "user":
                            msg_files = msg.get("files", [])
                        elif isinstance(msg, HumanMessage) and hasattr(msg, "additional_kwargs"):
                            msg_files = msg.additional_kwargs.get("files", [])

                        names = [f.get("name") for f in msg_files if isinstance(f, dict) and f.get("name")]
                        if names:
                            target_sources = names
                            break

        active_search_tool = create_hybrid_retriever_tool(
            vector_store, session_dir, filter_sources=target_sources
        )

        try:
            context = await active_search_tool.ainvoke(search_query)
        except Exception as exc:
            logger.error("Forced retrieval failed: %s", exc)
            context = "Retrieval failed."

        _update_streamlit_state("last_agent_path", "retrieval")

        # Build messages: ToolMessage for the tool call
        new_msgs = []
        if tool_call_id:
            new_msgs.append(ToolMessage(content=context, tool_call_id=tool_call_id))

        return {
            "messages": new_msgs,
            "context_used": context,
            "agent_path": "retrieval",
            "retrieved_docs": [context],
        }

    async def respond(state: AgentState):
        """Generate final answer using retrieved context."""
        _update_streamlit_state("last_agent_path", "retrieval")
        _update_streamlit_state("last_model_calls", state.get("model_call_count", 0) + 1)

        context_used = state.get("context_used", "")

        if context_used and context_used != "No relevant documents found.":
            prompt = (
                "You are an AI research assistant. You are provided with retrieved context from uploaded documents.\n\n"
                "INSTRUCTIONS:\n"
                "1. First check if the retrieved context below contains information relevant to the user's question.\n"
                "2. If the retrieved context contains the answer, answer the question accurately based on the context.\n"
                "3. If the user's question is NOT mentioned or covered in the retrieved context (e.g. general questions like 'Tell me about transformers'), state clearly that it is not mentioned in the uploaded documents, and then provide a complete, helpful answer using your general knowledge.\n"
                "4. Do NOT say 'sorry' or 'I apologize'.\n"
                "5. Do NOT list sources at the end of your response — citations are handled separately by the UI.\n\n"
                f"=== RETRIEVED CONTEXT ===\n{context_used}\n=========================="
            )
        else:
            prompt = (
                "No document context was retrieved. Answer using your general knowledge, "
                "but clearly state that the answer is NOT based on uploaded documents. "
                "NEVER say 'sorry' or apologize."
            )

        # Focus exclusively on the latest user question for the current turn to avoid confusing the LLM with old URL questions
        latest_user = None
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage) and msg.content:
                latest_user = msg
                break
            elif isinstance(msg, dict) and msg.get("role") == "user" and msg.get("content"):
                latest_user = HumanMessage(content=msg["content"])
                break

        user_messages = [latest_user] if latest_user else []
        messages = [SystemMessage(content=prompt)] + user_messages
        response = await _invoke_llm(llm, messages)
        return {"messages": [response], "agent_path": "retrieval"}

    # ---- Routing ----

    def route_after_input_check(state: AgentState):
        if state.get("blocked_reason"):
            return END
        return "rate_limit_check"

    def route_after_rate_limit(state: AgentState):
        if state.get("model_call_count", 0) > state.get("max_model_calls", 5):
            return END
        return "agent_decision"

    def route_after_agent(state: AgentState):
        if has_documents:
            return "force_retrieve"
        return END

    # ---- Assemble ----

    workflow = StateGraph(AgentState)
    workflow.add_node("check_input", check_input)
    workflow.add_node("rate_limit_check", rate_limit_check)
    workflow.add_node("agent_decision", agent_decision)
    workflow.add_node("force_retrieve", force_retrieve)
    workflow.add_node("respond", respond)

    workflow.add_edge(START, "check_input")
    workflow.add_conditional_edges(
        "check_input", route_after_input_check,
        {"rate_limit_check": "rate_limit_check", END: END},
    )
    workflow.add_conditional_edges(
        "rate_limit_check", route_after_rate_limit,
        {"agent_decision": "agent_decision", END: END},
    )
    workflow.add_conditional_edges(
        "agent_decision", route_after_agent,
        {"force_retrieve": "force_retrieve", END: END},
    )
    workflow.add_edge("force_retrieve", "respond")
    workflow.add_edge("respond", END)

    graph = workflow.compile()
    return graph


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def extract_result_metadata(result: dict) -> tuple[str, dict]:
    from helpers import clean_response

    model_name = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
    if not result:
        return "I could not generate a response.", {"model": model_name}

    answer = getattr(result["messages"][-1], "content", "I could not generate a response.")
    answer = clean_response(answer)

    metadata = {"model": model_name}

    context = result.get("context_used", "")
    if context and context != "No relevant documents found.":
        sources = []
        seen = set()
        answer_lower = answer.lower()
        stopwords = {
            "this", "that", "with", "from", "have", "about", "which", "there", "their",
            "where", "would", "could", "should", "project", "system", "using", "also",
            "been", "were", "more", "such", "other", "into", "first", "after", "then",
        }

        for m in re.finditer(r"\[Source \d+: (.+?)(?: \(page ([^)]+)\))?\]\n([\s\S]*?)(?=\[Source \d+:|$)", context):
            name = m.group(1).strip()
            page = m.group(2)
            chunk_text = m.group(3).strip()

            name_lower = name.lower()
            chunk_keywords = set(w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", chunk_text))
            answer_keywords = set(w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", answer_lower))

            meaningful_overlap = (chunk_keywords & answer_keywords) - stopwords

            # Keep source if its text meaningfully contributed to the answer or if the source is named in answer
            if len(meaningful_overlap) >= 2 or Path(name).name.lower() in answer_lower:
                if (name, page) not in seen:
                    seen.add((name, page))
                    sources.append({"name": name, "page": page})

        is_not_found = any(phrase in answer_lower for phrase in [
            "not mentioned in", "no mention of", "not found in", "not present in",
            "does not contain", "does not mention", "isn't mentioned", "is not in the provided"
        ])

        # Fallback: if strict filtering removed all and the response is not a 'not found' message, show sources
        if not sources and not is_not_found:
            for m in re.finditer(r"\[Source \d+: (.+?)(?: \(page ([^)]+)\))?\]", context):
                name, page = m.group(1).strip(), m.group(2)
                if (name, page) not in seen:
                    seen.add((name, page))
                    sources.append({"name": name, "page": page})

        if sources and not is_not_found:
            metadata["sources"] = sources

    docs = result.get("retrieved_docs", [])
    if docs:
        metadata["chunks"] = len(docs)

    # Store context and question for RAGAS evaluation
    if context and context != "No relevant documents found.":
        # Strip [Source N:] markers for clean RAGAS input
        clean_ctx = re.sub(r"\[Source \d+:.*?\]\n?", "", context).strip()
        if clean_ctx:
            metadata["context_used"] = clean_ctx

    # Extract last user question from messages
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) and not isinstance(msg, ToolMessage):
            metadata["question"] = msg.content
            break
        elif isinstance(msg, dict) and msg.get("role") == "user" and msg.get("content"):
            metadata["question"] = msg["content"]
            break

    return answer, metadata


async def run_agent_pipeline(
    vector_store,
    messages: list[dict],
    file_names: list[str],
    url_names: list[str],
    session_dir: str = "",
    on_step=None,
) -> tuple[str, dict]:
    """Run the agent graph asynchronously and return (answer, metadata)."""
    import time
    import asyncio

    graph = build_agent_graph(vector_store, session_dir)

    pipeline_start = time.time()
    step_timings = []
    current_step_start = None
    current_step_name = None

    def _start_step(name):
        nonlocal current_step_start, current_step_name
        current_step_start = time.time()
        current_step_name = name

    def _end_step():
        nonlocal current_step_start, current_step_name
        if current_step_start and current_step_name:
            elapsed = time.time() - current_step_start
            step_timings.append({"step": current_step_name, "ms": round(elapsed * 1000)})
            current_step_start = None
            current_step_name = None

    result = None
    async for event in graph.astream(
        {
            "messages": messages,
            "file_names": file_names,
            "url_names": url_names,
        },
        stream_mode="updates",
    ):
        if not result:
            result = {
                "messages": list(messages),
                "file_names": list(file_names),
                "url_names": list(url_names),
                "retrieved_docs": [],
                "sources": [],
                "model_call_count": 0,
                "max_model_calls": 5,
                "blocked_reason": None,
                "agent_path": "direct",
                "context_used": "",
            }

        for node_name, updates in event.items():
            _end_step()
            _start_step(node_name)

            if "messages" in updates:
                result["messages"].extend(updates["messages"])
            for k, v in updates.items():
                if k != "messages":
                    result[k] = v

            if on_step is not None:
                if node_name == "agent_decision":
                    on_step(2, node_name)
                elif node_name == "force_retrieve":
                    on_step(3, node_name)
                elif node_name == "respond":
                    on_step(4, node_name)

        await asyncio.sleep(0.01)

    _end_step()
    total_ms = round((time.time() - pipeline_start) * 1000)

    answer, metadata = extract_result_metadata(result)

    # Build trace data for UI
    trace_data = {
        "steps": step_timings,
        "total_ms": total_ms,
        "model": os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
        "path": result.get("agent_path", "direct"),
        "blocked": result.get("blocked_reason") is not None,
        "context_snippet": (result.get("context_used", "")[:300] + "...") if result.get("context_used") else "",
    }
    metadata["trace"] = trace_data

    return answer, metadata


def evaluate_ragas(question: str, answer: str, context: str, progress_callback=None) -> tuple[dict | None, str | None]:
    """Run RAGAS evaluation on a single question-answer-context triple.

    Args:
        question: The user's question.
        answer: The assistant's answer.
        context: The retrieved context text.
        progress_callback: Optional callable(progress: float, label: str) called
            after each metric (0.33, 0.66, 1.0).

    Returns (scores, err_msg) tuple:
        scores: {"faithfulness": float, "answer_relevancy": float, "context_precision": float} or None
        err_msg: Error message string or None
    """
    try:
        from ragas import evaluate
        from ragas.run_config import RunConfig
        from ragas.metrics import faithfulness, answer_relevancy, context_precision
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from datasets import Dataset

        if not question or not answer or not context:
            return None, "Missing required input (question, answer, or document context)."

        # Split context into individual passages. Cap the passage count:
        # context_precision makes one LLM call PER passage.
        context_passages = [p.strip() for p in re.split(r"\n{2,}", context) if p.strip()]
        if not context_passages:
            context_passages = [context]
        context_passages = context_passages[:4]

        eval_dataset = Dataset.from_dict({
            "question": [question],
            "answer": [answer],
            "contexts": [context_passages],
            "ground_truth": [answer],  # placeholder, not used by these 3 metrics
        })

        # Prefer Groq — it is far faster than the OpenRouter free-tier model.
        # (Wrapping with LangchainLLMWrapper avoids the OPENAI_API_KEY clash
        # that RAGAS's default OpenAI client has with a Groq key.)
        from langchain_groq import ChatGroq
        eval_llm = None
        groq_key = os.environ.get("GROQ_API_KEY")
        if not groq_key:
            try:
                import streamlit as st
                if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
                    groq_key = st.secrets["GROQ_API_KEY"]
            except Exception:
                pass

        if groq_key:
            eval_llm = ChatGroq(
                model=os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
                api_key=groq_key,
                temperature=0.0,
            )
        if eval_llm is None:
            eval_llm = _get_fallback_llm()
        if eval_llm is None:
            logger.warning("No LLM available for RAGAS evaluation")
            return None, "GROQ_API_KEY is not configured in environment or Streamlit Secrets."

        llm_wrapper = LangchainLLMWrapper(eval_llm)
        from rag_engine import _get_embeddings
        emb_wrapper = LangchainEmbeddingsWrapper(_get_embeddings())

        # Set LLM and embeddings on each metric
        faithfulness.llm = llm_wrapper
        answer_relevancy.llm = llm_wrapper
        answer_relevancy.embeddings = emb_wrapper
        context_precision.llm = llm_wrapper

        run_config = RunConfig(timeout=60, max_retries=3, max_wait=15)

        if progress_callback:
            progress_callback(0.15, "Evaluating all metrics in parallel...")

        # Isolate evaluate() in a dedicated worker thread with its own asyncio event loop
        # to prevent loop conflicts with Streamlit's runtime thread on Linux/Streamlit Cloud.
        import concurrent.futures
        def _run_eval_job():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return evaluate(
                    dataset=eval_dataset,
                    metrics=[faithfulness, answer_relevancy, context_precision],
                    run_config=run_config,
                )
            finally:
                loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_eval_job)
            result = future.result(timeout=75)

        def _extract(res, key):
            """Extract a score regardless of RAGAS version."""
            try:
                if hasattr(res, "_repr_dict"):
                    return float(res._repr_dict.get(key, 0.0))
                if hasattr(res, "scores") and res.scores:
                    return float(res.scores[0].get(key, 0.0))
                if hasattr(res, "items"):
                    return float(res.get(key, 0.0))
                return float(getattr(res, key, 0.0))
            except (TypeError, ValueError):
                return 0.0

        scores = {
            key: _extract(result, key)
            for key in ("faithfulness", "answer_relevancy", "context_precision")
        }

        if progress_callback:
            progress_callback(1.0, "Complete")

        return (scores, None) if scores else (None, "RAGAS evaluation yielded empty scores.")

    except Exception as e:
        logger.error("RAGAS evaluation failed: %s", e, exc_info=True)
        return None, str(e)
