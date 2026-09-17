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


def _get_supabase_headers() -> tuple[str, dict] | None:
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_KEY", "").strip()
    if not url or not key:
        return None
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    return url, headers


def _sync_session_to_supabase(session_id: str, data: dict) -> bool:
    config = _get_supabase_headers()
    if not config:
        return False
    url, headers = config

    user_id = data.get("user_id")
    if not user_id or len(str(user_id)) < 30:
        return False

    messages = data.get("messages", [])
    first_user = next(
        (m.get("content", "") for m in messages if isinstance(m, dict) and m.get("role") == "user"),
        "New Chat",
    ).strip()
    title = first_user[:40] + ("…" if len(first_user) > 40 else "")

    payload = {
        "session_id": session_id,
        "user_id": user_id,
        "title": title or "New Chat",
        "messages": messages,
        "files": data.get("uploaded_file_names", []),
        "updated_at": data.get("updated_at") or datetime.now().isoformat(),
    }

    try:
        import httpx
        post_headers = dict(headers)
        post_headers["Prefer"] = "resolution=merge-duplicates"
        with httpx.Client(timeout=3.0) as client:
            resp = client.post(f"{url}/rest/v1/conversations", json=payload, headers=post_headers)
            return resp.status_code in (200, 201, 204)
    except Exception as exc:
        logger.debug("Supabase session sync skipped: %s", exc)
        return False


def _load_session_from_supabase(session_id: str) -> dict:
    config = _get_supabase_headers()
    if not config:
        return {}
    url, headers = config

    try:
        import httpx
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{url}/rest/v1/conversations?session_id=eq.{session_id}", headers=headers)
            if resp.status_code == 200:
                items = resp.json()
                if items and isinstance(items, list):
                    row = items[0]
                    return {
                        "user_id": row.get("user_id"),
                        "messages": row.get("messages", []),
                        "uploaded_file_names": row.get("files", []),
                        "ingested_urls": [],
                        "chunk_count": len(row.get("files", [])),
                        "updated_at": row.get("updated_at"),
                    }
    except Exception as exc:
        logger.debug("Supabase load session skipped: %s", exc)
    return {}


def _list_supabase_conversations(user_id: str) -> list[dict]:
    config = _get_supabase_headers()
    if not config or not user_id or len(str(user_id)) < 30:
        return []
    url, headers = config

    try:
        import httpx
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(
                f"{url}/rest/v1/conversations?user_id=eq.{user_id}&order=updated_at.desc&limit=25",
                headers=headers,
            )
            if resp.status_code == 200:
                rows = resp.json()
                results = []
                for row in rows:
                    messages = row.get("messages", [])
                    last = messages[-1].get("content", "") if messages else ""
                    results.append({
                        "id": row.get("session_id"),
                        "title": row.get("title", "New Chat"),
                        "preview": last[:55] + ("…" if len(last) > 55 else ""),
                        "updated": row.get("updated_at") or "",
                    })
                return results
    except Exception as exc:
        logger.debug("Supabase list conversations skipped: %s", exc)
    return []


def _delete_session_from_supabase(session_id: str) -> None:
    config = _get_supabase_headers()
    if not config:
        return
    url, headers = config
    try:
        import httpx
        with httpx.Client(timeout=3.0) as client:
            client.delete(f"{url}/rest/v1/conversations?session_id=eq.{session_id}", headers=headers)
    except Exception:
        pass


def load_session(session_id: str) -> dict:
    """Read and parse a session's metadata from disk, falling back to Supabase cloud if needed."""
    path = session_metadata_path(session_id)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass

    cloud_data = _load_session_from_supabase(session_id)
    if cloud_data:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(cloud_data, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return cloud_data
    return {}


def save_session(
    session_id: str,
    messages: list,
    uploaded_file_names: list,
    ingested_urls: list,
    chunk_count: int,
    user_id: str | None = None,
) -> None:
    """Persist session data to disk and sync to Supabase PostgreSQL if configured."""
    data = {
        "user_id": user_id,
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

    _sync_session_to_supabase(session_id, data)


def delete_session(session_id: str) -> None:
    """Delete a session directory from disk and Supabase cloud."""
    session_dir = SESSIONS_DIR / session_id
    if session_dir.exists():
        try:
            shutil.rmtree(session_dir)
        except Exception:
            pass
    _delete_session_from_supabase(session_id)


def conversation_history(user_id: str | None = None) -> list[dict]:
    """Return saved conversations, scoped to user_id, merging local and Supabase cloud history."""
    conversations_map = {}

    for file in SESSIONS_DIR.glob("*/metadata.json"):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            if user_id and data.get("user_id") and data.get("user_id") != user_id:
                continue
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
            sid = file.parent.name
            conversations_map[sid] = {
                "id": sid,
                "title": first_user[:30] + ("…" if len(first_user) > 30 else ""),
                "preview": last[:55] + ("…" if len(last) > 55 else ""),
                "updated": updated,
            }
        except (OSError, json.JSONDecodeError, ValueError):
            continue

    if user_id:
        cloud_convs = _list_supabase_conversations(user_id)
        for c in cloud_convs:
            cid = c.get("id")
            if cid and cid not in conversations_map:
                conversations_map[cid] = c

    return sorted(conversations_map.values(), key=lambda item: item["updated"], reverse=True)
