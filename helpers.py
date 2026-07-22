"""Pure helper functions with zero Streamlit dependency.

Contains UI rendering helpers, session persistence, and request rate limiting.
"""

import base64
import html
import json
import os
import re
import shutil
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import markdown

ROOT = Path(__file__).parent
BACKGROUND_PATH = ROOT / "assets" / "agentic-rag-background.png"

SESSIONS_DIR = ROOT / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

# Rate Limiter settings
MAX_REQUESTS = 8        # allowed prompts...
WINDOW_SECONDS = 60     # ...per rolling window per session
_history: dict[str, list[float]] = defaultdict(list)


# ---------------------------------------------------------------------------
# UI & Formatting Helpers
# ---------------------------------------------------------------------------

def background_data_url() -> str:
    """Embed the supplied background in CSS so Streamlit serves it reliably."""
    if not BACKGROUND_PATH.exists():
        return ""
    encoded = base64.b64encode(BACKGROUND_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def esc(value: object) -> str:
    """HTML-escape a value for safe embedding in HTML."""
    return html.escape(str(value), quote=True)


def human_time(value: str) -> str:
    """Convert an ISO datetime string to a human-readable relative time."""
    try:
        date = datetime.fromisoformat(value)
    except ValueError:
        return ""
    delta = datetime.now() - date
    if delta.days == 0:
        return date.strftime("%I:%M %p").lstrip("0")
    if delta.days == 1:
        return "Yesterday"
    return f"{delta.days}d ago"


def clean_response(text: str) -> str:
    """Remove apologetic phrases from the assistant response."""
    patterns = [
        r"(?i)\bI'm sorry\b[.,!]*\s*",
        r"(?i)\bI apologize\b[.,!]*\s*",
        r"(?i)\bI made an incorrect assumption\b[.,!]*\s*",
        r"(?i)\bIt seems that I made an incorrect assumption\b[.,!]*\s*",
        r"(?i)\bSorry\b[.,!]*\s*",
        r"(?i)\bUnfortunately\b[.,!]*\s*",
    ]
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned)
    cleaned = re.sub(r"(?im)^\s*\**sources:?\**\s*(\[.*|\S.*)?$", "", cleaned)
    return cleaned.strip()


def render_reasoning(step_idx: int) -> str:
    """Generate HTML for the reasoning progress indicator."""
    steps = [
        "Analyzing request",
        "Checking safety",
        "Searching knowledge base",
        "Retrieving context",
        "Generating response",
    ]
    html_parts = ['<div class="reasoning"><div class="reasoning-title">\u2727 Reasoning:</div>']
    for i, step in enumerate(steps):
        if i < step_idx:
            html_parts.append(f'<span class="reasoning-step completed">\u2713 {step}</span>')
        elif i == step_idx:
            html_parts.append(f'<span class="reasoning-step active">\u25cf {step}</span>')
        else:
            html_parts.append(f'<span class="reasoning-step pending">\u203a {step}</span>')
    html_parts.append("</div>")
    return "".join(html_parts)


def render_indexing_status(label: str) -> str:
    """Generate HTML for live document/URL indexing status indicator."""
    return (
        f'<div class="reasoning">'
        f'<div class="reasoning-title">\u2727 Document Ingestion:</div>'
        f'<span class="reasoning-step active">\u25cf {esc(label)}</span>'
        f'</div>'
    )


def _citation_icon(name: str) -> str:
    """Pick an icon for a citation based on the source name."""
    lower = name.lower()
    if lower.startswith("http"):
        return "\U0001f517"
    if lower.endswith(".pdf"):
        return "\U0001f4d5"
    if lower.endswith(".docx"):
        return "\U0001f4d8"
    if lower.endswith(".pptx"):
        return "\U0001f4fd"
    if lower.endswith(".csv"):
        return "\U0001f4ca"
    if lower.endswith(".md"):
        return "\U0001f4dd"
    return "\U0001f4c4"


def build_citations_html(sources) -> str:
    """Render sources as numbered citation chips."""
    if not sources:
        return ""
    chips = []
    for i, src in enumerate(sources, 1):
        if isinstance(src, dict):
            name, page = src.get("name", "unknown"), src.get("page")
        else:
            name, page = str(src), None
        display = name if len(name) <= 42 else name[:39] + "..."
        page_html = f'<span class="citation-page">p. {esc(page)}</span>' if page else ""
        chips.append(
            f'<span class="citation-chip" title="{esc(name)}">'
            f'<span class="citation-num">{i}</span>'
            f'<span class="citation-icon">{_citation_icon(name)}</span>'
            f'<span class="citation-name">{esc(display)}</span>{page_html}</span>'
        )
    return (
        '<div class="citations"><span class="citations-label">Sources</span>'
        + "".join(chips) + "</div>"
    )


def build_metadata_badges(metadata: dict) -> str:
    """Build HTML for metadata badges from a metadata dict."""
    badges = []
    conf = metadata.get("confidence")
    if conf is not None:
        badges.append(f'<span>Confidence <b>{conf}%</b></span>')
    chunks = metadata.get("chunks")
    if chunks is not None:
        badges.append(f'<span><b>{chunks}</b> Chunks Retrieved</span>')
    model = metadata.get("model")
    if model:
        badges.append(f'<span>Model: <b>{esc(model)}</b></span>')
    trace = metadata.get("trace")
    if trace:
        total_ms = trace.get("total_ms", 0)
        badges.append(f'<span>\u26a1 <b>{total_ms}ms</b></span>')
        path = trace.get("path", "")
        if path:
            badges.append(f'<span>Path: <b>{esc(path)}</b></span>')
    if badges:
        return f'<div class="metadata">{"".join(badges)}</div>'
    return ""


def build_assistant_html(text: str, metadata: dict) -> str:
    """Build the full HTML for an assistant message card."""
    rendered = markdown.markdown(text, extensions=["fenced_code", "tables"])
    citations_html = build_citations_html(metadata.get("sources"))
    badge_html = build_metadata_badges(metadata)
    return (
        f'<div class="message-assistant"><div class="assistant-avatar">\U0001f9e0</div>'
        f'<div class="assistant-card">{rendered}{citations_html}{badge_html}</div></div>'
    )


def format_file_size(size_bytes: int) -> str:
    """Format a file size in bytes to a human-readable string."""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / 1024:.0f} KB"


def build_ragas_badges(scores: dict) -> str:
    """Build HTML for RAGAS evaluation score badges."""
    if not scores:
        return ""
    badges = []
    metrics = [
        ("faithfulness", "Faithfulness"),
        ("answer_relevancy", "Relevancy"),
        ("context_precision", "Precision"),
    ]
    for key, label in metrics:
        score = scores.get(key)
        if score is not None:
            if score >= 0.7:
                color = "#22c55e"
            elif score >= 0.4:
                color = "#eab308"
            else:
                color = "#ef4444"
            badges.append(
                f'<span class="ragas-badge" style="border-color:{color}40;background:{color}10">'
                f'<b style="color:{color}">{score:.0%}</b> {label}</span>'
            )
    if badges:
        return f'<div class="metadata ragas-scores">{"".join(badges)}</div>'
    return ""


def extract_url_from_prompt(prompt: str) -> tuple[str, str | None]:
    """Extract a URL from the prompt text. Returns (cleaned_prompt, url)."""
    url_match = re.search(r"https?://[^\s]+", prompt)
    if url_match:
        url = url_match.group(0)
        cleaned = prompt.replace(url, "").strip()
        return cleaned, url
    return prompt, None


# ---------------------------------------------------------------------------
# Session Persistence Helpers
# ---------------------------------------------------------------------------

def session_path(session_id: str) -> Path:
    """Return the directory for a session, creating it if needed."""
    path = SESSIONS_DIR / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def session_metadata_path(session_id: str) -> Path:
    """Return the path to a session's metadata.json."""
    return session_path(session_id) / "metadata.json"


def load_session(session_id: str) -> dict:
    """Read and parse a session's metadata from disk."""
    path = session_metadata_path(session_id)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_session(
    session_id: str,
    messages: list,
    uploaded_file_names: list,
    ingested_urls: list,
    chunk_count: int,
) -> None:
    """Persist session data to disk."""
    data = {
        "messages": messages,
        "uploaded_file_names": uploaded_file_names,
        "ingested_urls": ingested_urls,
        "chunk_count": chunk_count,
        "updated_at": datetime.now().isoformat(),
    }
    try:
        session_metadata_path(session_id).write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def delete_session(session_id: str) -> None:
    """Delete a session directory from disk."""
    session_dir = SESSIONS_DIR / session_id
    if session_dir.exists():
        try:
            shutil.rmtree(session_dir)
        except Exception:
            pass


def conversation_history() -> list[dict]:
    """Return saved conversations, newest first."""
    conversations = []
    for file in SESSIONS_DIR.glob("*/metadata.json"):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            messages = data.get("messages", [])
            first_user = next(
                (m.get("content", "") for m in messages if m.get("role") == "user"),
                "",
            ).strip()
            if not first_user:
                continue
            last = messages[-1].get("content", "") if messages else ""
            updated = data.get("updated_at") or datetime.fromtimestamp(
                file.stat().st_mtime
            ).isoformat()
            conversations.append(
                {
                    "id": file.parent.name,
                    "title": first_user[:30] + ("\u2026" if len(first_user) > 30 else ""),
                    "preview": last[:55] + ("\u2026" if len(last) > 55 else ""),
                    "updated": updated,
                }
            )
        except (OSError, json.JSONDecodeError, ValueError):
            continue
    return sorted(conversations, key=lambda item: item["updated"], reverse=True)


# ---------------------------------------------------------------------------
# Rate Limiting Helpers
# ---------------------------------------------------------------------------

def _prune_rate_limit(session_id: str, now: float) -> None:
    cutoff = now - WINDOW_SECONDS
    _history[session_id] = [t for t in _history[session_id] if t > cutoff]


def check_rate_limit(session_id: str) -> tuple[bool, float]:
    """Check request limit for session. Returns (allowed, retry_after_seconds)."""
    now = time.monotonic()
    _prune_rate_limit(session_id, now)
    timestamps = _history[session_id]

    if len(timestamps) >= MAX_REQUESTS:
        retry_after = WINDOW_SECONDS - (now - timestamps[0])
        return False, max(retry_after, 1.0)

    timestamps.append(now)
    return True, 0.0


def rate_limit_remaining(session_id: str) -> int:
    """Return remaining allowed prompts in the current window."""
    _prune_rate_limit(session_id, time.monotonic())
    return max(0, MAX_REQUESTS - len(_history[session_id]))


def reset_rate_limit(session_id: str) -> None:
    """Clear rate limit history for a session."""
    _history.pop(session_id, None)
