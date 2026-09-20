"""UI rendering helpers, formatting, and session persistence."""

import base64
import html
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

import logging
import markdown

logger = logging.getLogger("ui")

ROOT = Path(__file__).resolve().parent.parent
BACKGROUND_PATH = ROOT / "assets" / "agentic-rag-background.png"
SESSIONS_DIR = ROOT / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# UI & Formatting Helpers
# ---------------------------------------------------------------------------

_cached_bg_data_url: str | None = None


def background_data_url() -> str:
    """Embed the background asset in CSS so Streamlit serves it reliably."""
    global _cached_bg_data_url
    if _cached_bg_data_url is not None:
        return _cached_bg_data_url
    if not BACKGROUND_PATH.exists():
        return ""
    encoded = base64.b64encode(BACKGROUND_PATH.read_bytes()).decode("ascii")
    _cached_bg_data_url = f"data:image/png;base64,{encoded}"
    return _cached_bg_data_url


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
    html_parts = ['<div class="reasoning"><div class="reasoning-title">✧ Reasoning:</div>']
    for i, step in enumerate(steps):
        if i < step_idx:
            html_parts.append(f'<span class="reasoning-step completed">✓ {step}</span>')
        elif i == step_idx:
            html_parts.append(f'<span class="reasoning-step active">● {step}</span>')
        else:
            html_parts.append(f'<span class="reasoning-step pending">› {step}</span>')
    html_parts.append("</div>")
    return "".join(html_parts)


def render_indexing_status(label: str) -> str:
    """Generate HTML for live document/URL indexing status indicator."""
    return (
        f'<div class="reasoning">'
        f'<div class="reasoning-title">✧ Document Ingestion:</div>'
        f'<span class="reasoning-step active">● {esc(label)}</span>'
        f'</div>'
    )


def _citation_icon(name: str) -> str:
    """Pick an icon for a citation based on the source name."""
    lower = name.lower()
    if lower.startswith("http"):
        return "🔗"
    if lower.endswith(".pdf"):
        return "📕"
    if lower.endswith(".docx"):
        return "📘"
    if lower.endswith(".pptx"):
        return "📽"
    if lower.endswith(".csv"):
        return "📊"
    if lower.endswith(".md"):
        return "📝"
    return "📄"


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
        badges.append(f'<span>⚡ <b>{total_ms}ms</b></span>')
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
        f'<div class="message-assistant"><div class="assistant-avatar">🧠</div>'
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
# Session Persistence (Delegated to deep core.session module)
# ---------------------------------------------------------------------------

from core.session import (
    session_path,
    session_metadata_path,
    load_session,
    save_session,
    delete_session,
    conversation_history,
    SESSIONS_DIR,
)

# ---------------------------------------------------------------------------
# Theme Engine (Delegated to deep core.theme module)
# ---------------------------------------------------------------------------

from core.theme import ThemeEngine, inject_theme, get_theme_css


