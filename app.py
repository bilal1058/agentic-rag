"""Streamlit interface for the Agentic RAG chatbot."""

import os
import time
import uuid
from datetime import datetime
import textwrap
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from core.config import get_runtime_config
from core.governance import startup_health_check, check_rate_limit, reset_rate_limit
from core.auth import (
    login_user,
    signup_user,
    logout_user,
    is_supabase_configured,
    evaluate_password_strength,
    update_user_name,
    get_google_auth_url,
    validate_token,
)
from core.oauth_component import oauth_bridge
from core.session import (
    session_path,
    load_session,
    save_session as persist_session,
    delete_session,
    conversation_history,
)
from core.pipeline import AssistantPipeline
from core.theme import inject_theme
from core.ui import (
    background_data_url,
    esc,
    human_time,
    render_reasoning,
    render_indexing_status,
    build_assistant_html,
    build_ragas_badges,
    extract_url_from_prompt,
    format_file_size,
)

load_dotenv()
RUNTIME_CONFIG = get_runtime_config()
startup_warnings = startup_health_check()


def _save() -> None:
    user_id = st.session_state.get("user", {}).get("id") if st.session_state.get("user") else None
    persist_session(
        st.session_state.session_id,
        st.session_state.messages,
        st.session_state.uploaded_file_names,
        st.session_state.ingested_urls,
        st.session_state.chunk_count,
        user_id=user_id,
    )


def stream_text(text: str, metadata: dict, placeholder) -> None:
    """Stream the assistant response to the UI word by word."""
    words = text.split(" ")
    current_text = ""
    for i, word in enumerate(words):
        current_text += (word if i == 0 else " " + word)
        placeholder.markdown(
            build_assistant_html(current_text, metadata),
            unsafe_allow_html=True,
        )
        time.sleep(0.012)


st.set_page_config(
    page_title="Agentic RAG Chatbot",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()

if "delete_session" in st.query_params:
    del_id = st.query_params["delete_session"]
    delete_session(del_id)
    current_session = st.query_params.get("session_id")
    new_params = {}
    if current_session and current_session != del_id:
        new_params["session_id"] = current_session
    st.query_params.clear()
    for k, v in new_params.items():
        st.query_params[k] = v
    st.rerun()


if st.session_state.get("user") and "session_id" not in st.query_params:
    st.query_params["session_id"] = str(uuid.uuid4())


session_id = str(st.query_params.get("session_id", ""))
saved = load_session(session_id)
if st.session_state.get("loaded_session") != session_id:
    st.session_state.loaded_session = session_id
    st.session_state.session_id = session_id
    st.session_state.messages = saved.get("messages", [])
    st.session_state.uploaded_file_names = saved.get("uploaded_file_names", [])
    st.session_state.ingested_urls = saved.get("ingested_urls", [])
    st.session_state.chunk_count = saved.get("chunk_count", 0)
    st.session_state.vector_store = None
    db_path = session_path(session_id) / "qdrant_db"
    if db_path.exists() and (st.session_state.uploaded_file_names or st.session_state.ingested_urls):
        try:
            from core.rag import get_qdrant_vector_store
            st.session_state.vector_store = get_qdrant_vector_store(str(db_path))
        except Exception:
            pass
    st.session_state.processing = None
    st.session_state.ragas_scores = {}
    st.session_state.ragas_pending = None
    st.session_state.delete_confirm = None


def new_chat() -> None:
    st.query_params["session_id"] = str(uuid.uuid4())


@st.dialog("Delete Conversation")
def show_delete_dialog():
    del_id = st.session_state.delete_confirm
    del_title = "this conversation"
    for item in conversation_history():
        if item["id"] == del_id:
            del_title = esc(item["title"])
            break
    st.markdown(
        f'<div style="text-align:center;padding:12px 0 8px;">'
        f'<div style="font-size:36px;margin-bottom:10px;">🗑️</div>'
        f'<div style="color:#f4f4f5;font-size:15px;font-weight:600;">Delete &ldquo;{del_title}&rdquo;?</div>'
        f'<div style="color:#a1a1aa;font-size:13px;margin-top:8px;">This action cannot be undone.</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancel", key="cancel_del", use_container_width=True):
            st.session_state.delete_confirm = None
            st.rerun()
    with c2:
        if st.button("Delete", key="confirm_del", use_container_width=True, type="primary"):
            delete_session(del_id)
            reset_rate_limit(del_id)
            st.session_state.delete_confirm = None
            if del_id == st.session_state.session_id:
                new_chat()
            st.rerun()


with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="brand-mark-outer"><div class="brand-mark">✦</div></div><div><div class="brand-name">Agentic RAG</div><div class="brand-badge-row"><span class="brand-tag">v2.5 PRO</span><span class="brand-status-dot"></span><span class="brand-subtitle">Neural Engine</span></div></div></div>',
        unsafe_allow_html=True,
    )
    if not st.session_state.get("user"):
        auth_mode_label = "☁️ Supabase" if is_supabase_configured() else "🔒 Local SQLite"
        st.info(f"Please sign in or create an account to start.\n\n**Auth Mode:** {auth_mode_label}")
    else:
        st.button("＋  New Chat", on_click=new_chat, use_container_width=True)
        search_term = st.text_input("Search conversations", placeholder="⌕  Search conversations...", label_visibility="collapsed")
        st.markdown('<div class="side-heading">Recent Chats</div>', unsafe_allow_html=True)
        user_id = st.session_state.user.get("id")
        matching_history = [
            item for item in conversation_history(user_id=user_id)
            if search_term.lower() in (item["title"] + " " + item["preview"]).lower()
        ]
        if matching_history:
            # Render chat cards as styled HTML
            html_cards = '<div class="chat-history-list">'
            for item in matching_history[:10]:
                is_active = item["id"] == st.session_state.session_id
                title = esc(item["title"])
                time_str = esc(human_time(item["updated"]))
                active_class = "active" if is_active else ""

                html_cards += textwrap.dedent(f"""\
                    <div class="chat-card {active_class}" data-id="{item['id']}">
                        <div class="chat-card-content">
                            <div class="chat-title">{title}</div>
                            <div class="chat-time">&bull; {time_str}</div>
                        </div>
                        <div class="chat-delete" title="Delete conversation">✕</div>
                    </div>
                """)
            html_cards += '</div>'
            st.markdown(html_cards, unsafe_allow_html=True)

            # Hidden Streamlit buttons for both select and delete
            for item in matching_history[:10]:
                if st.button(f"HIDDEN_SEL_{item['id']}", key=f"chat_{item['id']}"):
                    st.query_params["session_id"] = item["id"]
                    st.rerun()
                if st.button(f"HIDDEN_DEL_{item['id']}", key=f"del_{item['id']}"):
                    st.session_state.delete_confirm = item["id"]
                    st.rerun()

            # JavaScript: hide hidden buttons & attach live event-delegation click handler
            st.html(
                """
            <script>
                function initChatCardListeners() {
                    document.querySelectorAll('button').forEach(btn => {
                        const t = btn.textContent;
                        if (t.startsWith('HIDDEN_SEL_') || t.startsWith('HIDDEN_DEL_')) {
                            const el = btn.closest('[data-testid="stButton"]');
                            if (el) el.style.display = 'none';
                        }
                    });
                    const container = document.querySelector('.chat-history-list');
                    if (container && !container.dataset.delegated) {
                        container.dataset.delegated = 'true';
                        container.addEventListener('click', (e) => {
                            const delBtn = e.target.closest('.chat-delete');
                            if (delBtn) {
                                e.stopPropagation();
                                e.preventDefault();
                                const card = delBtn.closest('.chat-card');
                                if (card) {
                                    const id = card.getAttribute('data-id');
                                    const btns = document.querySelectorAll('button');
                                    const targetBtn = Array.from(btns).find(b => b.textContent === 'HIDDEN_DEL_' + id);
                                    if (targetBtn) targetBtn.click();
                                }
                                return;
                            }
                            const card = e.target.closest('.chat-card');
                            if (card) {
                                const id = card.getAttribute('data-id');
                                const btns = document.querySelectorAll('button');
                                const targetBtn = Array.from(btns).find(b => b.textContent === 'HIDDEN_SEL_' + id);
                                if (targetBtn) targetBtn.click();
                            }
                        });
                    }
                }
                initChatCardListeners();
                setTimeout(initChatCardListeners, 80);
            </script>
            """,
                unsafe_allow_javascript=True,
            )
        else:
            st.markdown('<div class="empty-history">No saved conversations yet.</div>', unsafe_allow_html=True)

        user = st.session_state.user
        user_email = user.get("email", "user@example.com")
        user_name = user.get("name") or user_email.split("@")[0].capitalize()
        initials = user_name[:2].upper() if user_name else "U"
        provider_badge = "☁️ Supabase" if user.get("provider") == "supabase" else "🔒 Local"

        # ChatGPT-style profile dropup menu at bottom of sidebar
        with st.popover(f"👤  {user_name}  ▾", use_container_width=True):
            st.markdown(
                f"""
                <div style="display:flex; align-items:center; gap:12px; padding:4px 0 10px; border-bottom:1px solid rgba(255,255,255,0.08);">
                  <div style="width:40px; height:40px; border-radius:50%; background:rgba(249,115,22,0.15); border:1px solid #f97316; display:grid; place-items:center; font-weight:700; color:#ff7a00; font-size:15px;">
                    {esc(initials)}
                  </div>
                  <div style="overflow:hidden;">
                    <div style="font-size:14px; font-weight:600; color:#f4f4f5; white-space:nowrap; text-overflow:ellipsis; overflow:hidden;">{esc(user_name)}</div>
                    <div style="font-size:11px; color:#a1a1aa; white-space:nowrap; text-overflow:ellipsis; overflow:hidden;">{esc(user_email)}</div>
                  </div>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin:10px 0 12px; font-size:12px;">
                  <span style="color:#71717a;">Auth Provider</span>
                  <span style="padding:2px 8px; border-radius:8px; background:rgba(255,115,0,0.12); color:#ff8800; border:1px solid rgba(255,115,0,0.25); font-weight:500; font-size:11px;">{provider_badge}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown('<div style="font-size:12px; font-weight:600; color:#d4d4d8; margin:6px 0 2px;">Account Details</div>', unsafe_allow_html=True)
            edit_name_val = st.text_input("Display Name", value=user_name, key="sidebar_edit_name_input", label_visibility="collapsed")
            if st.button("💾 Update Name", key="btn_save_name_sidebar", use_container_width=True):
                if edit_name_val.strip() and edit_name_val.strip() != user_name:
                    if update_user_name(user, edit_name_val.strip()):
                        st.session_state.user["name"] = edit_name_val.strip()
                        st.toast("Profile name updated!", icon="✨")
                        st.rerun()
                    else:
                        st.error("Could not update name.")

            st.markdown('<div style="height:1px; background:rgba(255,255,255,0.08); margin:10px 0 8px;"></div>', unsafe_allow_html=True)
            if st.button("🚪 Sign Out", key="sidebar_popover_logout_btn", use_container_width=True, type="secondary"):
                logout_user(user.get("token", ""))
                st.session_state.user = None
                st.session_state.just_logged_out = True
                oauth_bridge(logout=True, key="oauth_token_logout")
                st.rerun()


# Delete confirmation modal (overlay at top of screen)
if st.session_state.get("delete_confirm"):
    show_delete_dialog()


# Authentication Gate
if not st.session_state.get("user"):
    # If user just logged out, actively trigger client token cleanup
    if st.session_state.get("just_logged_out"):
        oauth_bridge(logout=True, key="oauth_token_bridge_logout")
        st.session_state.pop("just_logged_out", None)
    else:
        # 1. Check browser cookies for persistent auth token
        cookie_token = None
        try:
            if hasattr(st, "context") and hasattr(st.context, "cookies"):
                cookie_token = (st.context.cookies or {}).get("agentic_auth_token")
        except Exception:
            pass

        if cookie_token:
            cookie_user = validate_token(cookie_token)
            if cookie_user:
                st.session_state.user = cookie_user
                st.rerun()

        # 2. Run the native OAuth bridge component (reads OAuth hash and passes token safely via postMessage)
        bridge_token = oauth_bridge(logout=False, key="oauth_token_bridge")
        if bridge_token:
            authed_user = validate_token(bridge_token)
            if authed_user:
                st.session_state.user = authed_user
                st.rerun()

    # 3. Check for OAuth callback access token in query parameters
    if st.query_params.get("access_token"):
        oauth_token = st.query_params.get("access_token")
        authed_user = validate_token(oauth_token)
        if authed_user:
            st.session_state.user = authed_user
            st.query_params.clear()
            st.rerun()
        else:
            st.query_params.clear()
            st.error("⚠️ Authentication session expired or invalid. Please sign in again.")

    # Clearable banner for OAuth errors (e.g. cancelled logins or bad state)
    if st.query_params.get("error") or st.query_params.get("error_description"):
        err_msg = st.query_params.get("error_description") or st.query_params.get("error")
        st.warning(f"⚠️ Sign-in notice: {err_msg}")
        if st.button("🔄 Clear & Try Again"):
            st.query_params.clear()
            st.rerun()

    auth_badge = "☁️ Supabase Cloud Active" if is_supabase_configured() else "🔒 Local SQLite Mode"
    configured_app_url = os.environ.get("APP_URL", "").strip()
    if configured_app_url:
        redirect_uri = configured_app_url
    else:
        host = ""
        try:
            if hasattr(st, "context") and hasattr(st.context, "headers"):
                host = (st.context.headers or {}).get("host", "")
        except Exception:
            pass
        if host and ("localhost" in host or "127.0.0.1" in host):
            redirect_uri = f"http://{host}/"
        else:
            redirect_uri = "https://agentic-rag-chat.streamlit.app/"
    google_oauth_url = get_google_auth_url(redirect_uri=redirect_uri)

    st.markdown(
        f"""
        <div id="auth-welcome-container" style="max-width: 480px; margin: 30px auto 16px; text-align: center;">
          <div class="auth-welcome-spark">✦</div>
          <div class="hero-eyebrow" style="margin-bottom: 8px;"><span class="hero-pulse"></span> ENTERPRISE INTELLIGENCE</div>
          <h1 style="font-family: var(--font-display); font-size: 42px; font-weight: 400; color: #ffffff; margin-bottom: 8px; letter-spacing: 0.05em; text-transform: uppercase;">Welcome to <span style="color:#ff7d00;">Agentic RAG</span></h1>
          <p style="color: #94a3b8; font-size: 14.5px; margin-bottom: 12px; line-height: 1.5;">Your enterprise research assistant with deep retrieval & reasoning.</p>
          <span style="font-size: 11.5px; padding: 4px 14px; border-radius: 999px; background: rgba(255,103,0,0.1); border: 1px solid rgba(255,103,0,0.3); color: #ffa338; font-weight: 600; font-family: var(--font-mono);">{auth_badge}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    auth_col1, auth_col2, auth_col3 = st.columns([1, 2, 1])
    with auth_col2:
        # Google OAuth Sign-in Button
        if is_supabase_configured() and google_oauth_url:
            st.markdown(
                f"""
                <div id="auth-google-section">
                  <a href="{google_oauth_url}" target="_blank" rel="noopener noreferrer" class="auth-google-btn">
                    <svg width="18" height="18" viewBox="0 0 24 24">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
                    </svg>
                    <span>Continue with Google</span>
                  </a>
                  <div style="display:flex; align-items:center; margin:12px 0 16px; color:#71717a; font-size:12px;">
                    <div style="flex:1; height:1px; background:rgba(255,255,255,0.08);"></div>
                    <span style="padding:0 12px; letter-spacing:0.5px; text-transform:uppercase; font-size:11px;">or continue with email</span>
                    <div style="flex:1; height:1px; background:rgba(255,255,255,0.08);"></div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        tab_login, tab_signup = st.tabs(["🔑 Sign In", "✨ Create Account"])

        with tab_login:
            with st.form("login_form"):
                login_email = st.text_input("Email address", placeholder="you@example.com", key="login_email_input")
                login_password = st.text_input("Password", type="password", placeholder="••••••••", key="login_pwd_input")
                login_submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

                if login_submitted:
                    try:
                        user_info = login_user(login_email, login_password)
                        st.session_state.user = user_info
                        st.success(f"Welcome back, {user_info.get('name') or user_info['email']}!")
                        st.rerun()
                    except ValueError as err:
                        st.error(str(err))

        with tab_signup:
            signup_name = st.text_input("Full Name", placeholder="e.g. Muhammad Bilal", key="signup_name_input")
            signup_email = st.text_input("Email address", placeholder="you@example.com", key="signup_email_input")
            signup_password = st.text_input("Create Password", type="password", placeholder="At least 8 characters", key="signup_pwd_input")

            # Real-time Password Strength Meter
            strength = evaluate_password_strength(signup_password)
            if signup_password:
                st.markdown(
                    f"""
                    <div style="margin: 6px 0 10px;">
                      <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:4px;">
                        <span style="color:#a1a1aa;">Password Strength</span>
                        <span style="color:{strength['color']}; font-weight:600;">{strength['label']}</span>
                      </div>
                      <div style="background: rgba(255,255,255,0.08); height: 5px; border-radius: 4px; overflow: hidden;">
                        <div style="width: {strength['percent']}%; background: {strength['color']}; height: 100%; transition: width 0.3s ease;"></div>
                      </div>
                    </div>
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 4px; font-size: 11px; margin-bottom: 12px; padding: 8px 10px; background: rgba(255,255,255,0.025); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px;">
                      <div style="color: {'#10b981' if strength['criteria']['length'] else '#71717a'};">
                        {'✓' if strength['criteria']['length'] else '✕'} 8+ characters
                      </div>
                      <div style="color: {'#10b981' if strength['criteria']['uppercase'] else '#71717a'};">
                        {'✓' if strength['criteria']['uppercase'] else '✕'} Uppercase (A-Z)
                      </div>
                      <div style="color: {'#10b981' if strength['criteria']['lowercase'] else '#71717a'};">
                        {'✓' if strength['criteria']['lowercase'] else '✕'} Lowercase (a-z)
                      </div>
                      <div style="color: {'#10b981' if strength['criteria']['digit'] else '#71717a'};">
                        {'✓' if strength['criteria']['digit'] else '✕'} Number (0-9)
                      </div>
                      <div style="color: {'#10b981' if strength['criteria']['special'] else '#71717a'}; grid-column: span 2;">
                        {'✓' if strength['criteria']['special'] else '✕'} Special symbol (!@#$%^&*)
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            signup_confirm = st.text_input("Confirm Password", type="password", placeholder="••••••••", key="signup_pwd_confirm")

            if st.button("Create Account", key="btn_create_account", use_container_width=True, type="primary"):
                if not signup_email:
                    st.error("Please enter a valid email address.")
                elif not signup_password:
                    st.error("Please enter a password.")
                elif signup_password != signup_confirm:
                    st.error("Passwords do not match.")
                elif not strength["is_valid"]:
                    st.error("Password is too weak. Please satisfy at least 4 security requirements.")
                else:
                    try:
                        user_info = signup_user(signup_email, signup_password, full_name=signup_name, enforce_strength=True)
                        st.session_state.user = user_info
                        st.success(f"Account created! Welcome, {user_info.get('name') or user_info['email']}!")
                        st.rerun()
                    except ValueError as err:
                        st.error(str(err))

    st.stop()

document_count = len(st.session_state.uploaded_file_names) + len(st.session_state.ingested_urls)
document_label = f"{document_count} Document{'s' if document_count != 1 else ''}"
chunk_count = st.session_state.get("chunk_count", 0)
chunk_badge = f'<span class="badge"><i>◫</i>{chunk_count:,} Chunks</span>' if chunk_count else ""
st.markdown(
    f"""
    <style>
    #oauth-instant-overlay {{ display: none !important; }}
    body.oauth-authenticating #oauth-instant-overlay {{ display: none !important; }}
    </style>
    <div class="hero">
      <div class="hero-eyebrow"><span class="hero-pulse"></span> ENTERPRISE REASONING &bull; HYBRID RETRIEVAL</div>
      <h1>AGENTIC <span>RAG</span> ASSISTANT</h1>
      <p>Advanced multi-hop reasoning over enterprise knowledge bases with verified citations and real-time safety guardrails.</p>
      <div class="badges">
        <span class="badge"><i>🛡️</i>Guardrails Active</span>
        <span class="badge"><i>⚡</i>Agentic Pipeline</span>
        <span class="badge"><i>📂</i>{document_label}</span>
        {chunk_badge}
      </div>
      <div style="margin-top: 16px; color: #64748b; font-size: 12px; font-family: var(--font-mono);">
        RUNTIME: <b style="color:#94a3b8;">{RUNTIME_CONFIG['app_env'].upper()}</b> &nbsp;|&nbsp; MODEL: <b style="color:#ffa338;">{RUNTIME_CONFIG['groq_model']}</b>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if startup_warnings:
    for warning in startup_warnings:
        st.warning(warning)

conversation = st.container()
with conversation:
    for msg_idx, message in enumerate(st.session_state.messages):
        if message.get("role") == "user":
            def _file_icon(file_type):
                ft = file_type.lower()
                if ft == "pdf":
                    return "pdf", "\U0001f4d5"
                elif ft == "url":
                    return "url", "\U0001f517"
                elif ft == "md":
                    return "md", "\U0001f4dd"
                elif ft == "csv":
                    return "csv", "\U0001f4ca"
                elif ft == "docx":
                    return "docx", "\U0001f4d8"
                elif ft == "txt":
                    return "txt", "\U0001f4c4"
                elif ft == "pptx":
                    return "pptx", "\U0001f4fd"
                return "default", "\U0001f4c4"
            files = ""
            for file in message.get("files", []):
                icon_class, icon_char = _file_icon(file.get("type", ""))
                files += (
                    f'<div class="file-card">'
                    f'<div class="file-icon {icon_class}">{icon_char}</div>'
                    f'<div><div class="file-name">{esc(file["name"])}</div>'
                    f'<div class="file-meta">{esc(file["type"])} \u00b7 {esc(file["size"])}</div></div>'
                    f'<span class="file-check">\u2713</span></div>'
                )
            content = esc(message.get("content", ""))
            st.markdown(
                f'<div class="message-user"><div class="user-bubble"><div class="user-header">You <span class="user-avatar">\u2659</span></div>{files}'
                f'<div class="user-content">{content}</div><div class="timestamp">{esc(message.get("timestamp", ""))}</div></div></div>',
                unsafe_allow_html=True,
            )
        elif message.get("role") == "assistant":
            st.markdown(
                build_assistant_html(message.get("content", ""), message.get("metadata", {})),
                unsafe_allow_html=True,
            )
            # Show RAGAS badges if scores exist
            if msg_idx in st.session_state.get("ragas_scores", {}):
                st.markdown(
                    build_ragas_badges(st.session_state.ragas_scores[msg_idx]),
                    unsafe_allow_html=True,
                )
            # Run RAGAS evaluation inline if this message is pending
            elif st.session_state.get("ragas_pending") == msg_idx:
                from core.rag import evaluate_ragas
                meta = message.get("metadata", {})
                question = meta.get("question", "")
                answer_text = message.get("content", "")
                context = meta.get("context_used", "")
                if not question:
                    for i in range(msg_idx - 1, -1, -1):
                        prev = st.session_state.messages[i]
                        if prev.get("role") == "user" and prev.get("content"):
                            question = prev["content"]
                            break
                if not context:
                    st.warning("Cannot evaluate: no retrieved context.")
                elif not question:
                    st.warning("Cannot evaluate: question not found.")
                else:
                    prog = st.progress(0.0, text="\U0001f4ca Computing Faithfulness...")
                    scores = evaluate_ragas(
                        question, answer_text, context,
                        progress_callback=lambda p, label: prog.progress(p, text=f"\U0001f4ca {label}"),
                    )
                    if scores:
                        prog.progress(1.0, text="\u2705 Complete")
                        st.session_state.ragas_scores[msg_idx] = scores
                    else:
                        st.markdown(
                            '<div class="ragas-progress-text" style="color:#ef4444;">\u26a0\ufe0f RAGAS evaluation failed</div>',
                            unsafe_allow_html=True,
                        )
                st.session_state.ragas_pending = None
                st.rerun()
            else:
                if st.button("\U0001f4ca Evaluate", key=f"ragas_{msg_idx}", help="Run RAGAS evaluation on this response"):
                    st.session_state.ragas_pending = msg_idx
                    st.rerun()
    streaming_placeholder = st.empty()


user_input = st.chat_input(
    "Ask a question or upload documents...",
    accept_file="multiple",
    file_type=["pdf", "md", "csv", "docx", "txt", "pptx"],
)

if user_input:
    uploaded = []
    for file in user_input.files or []:
        uploaded.append({"name": file.name, "type": Path(file.name).suffix.lstrip(".").upper() or "FILE", "size": format_file_size(file.size)})
    prompt = (user_input.text or "").strip()
    prompt, pending_url = extract_url_from_prompt(prompt)
    if pending_url:
        uploaded.append({"name": pending_url, "type": "URL", "size": "Link"})
    if prompt or uploaded:
        # Rate-limit only actual questions (prompts), not pure uploads.
        if prompt:
            allowed, retry_after = check_rate_limit(st.session_state.session_id)
            if not allowed:
                st.toast(
                    f"⏳ You're sending questions too quickly. "
                    f"Please wait {int(retry_after)}s and try again.",
                    icon="⏳",
                )
                st.stop()
        st.session_state.messages.append(
            {"role": "user", "content": prompt, "files": uploaded, "timestamp": datetime.now().strftime("%I:%M %p").lstrip("0")}
        )
        st.session_state.processing = {"files": user_input.files, "prompt": prompt, "url": pending_url}
        _save()
        st.rerun()


if st.session_state.get("processing"):
    task = st.session_state.processing
    status = st.empty()

    # Pre-render initial status bar INSTANTLY (0ms) so user never sees a blank gap
    if task.get("url"):
        status.markdown(render_indexing_status(f"Fetching and scraping web page: {task['url']}"), unsafe_allow_html=True)
    elif task.get("files"):
        status.markdown(render_indexing_status("Reading uploaded files..."), unsafe_allow_html=True)
    elif task.get("prompt"):
        status.markdown(render_reasoning(0), unsafe_allow_html=True)

    def indexing_progress(progress: float, label: str):
        status.markdown(render_indexing_status(label), unsafe_allow_html=True)

    try:
        session_dir = session_path(st.session_state.session_id)

        if task.get("files"):
            status.markdown(render_indexing_status("Reading uploaded files..."), unsafe_allow_html=True)
            store, count = AssistantPipeline.ingest_files(
                task["files"],
                session_dir=session_dir,
                existing_store=st.session_state.vector_store,
                on_progress=indexing_progress,
            )
            if store is not None:
                st.session_state.vector_store = store
            if count:
                st.session_state.chunk_count += count
                st.session_state.uploaded_file_names.extend(file.name for file in task["files"])

        if task.get("url"):
            status.markdown(render_indexing_status(f"Fetching and scraping web page: {task['url']}"), unsafe_allow_html=True)
            store, count = AssistantPipeline.ingest_url(
                task["url"],
                session_dir=session_dir,
                existing_store=st.session_state.vector_store,
                on_progress=indexing_progress,
            )
            if store is not None:
                st.session_state.vector_store = store
            if count:
                st.session_state.chunk_count += count
                st.session_state.ingested_urls.append(task["url"])

        if task.get("prompt"):
            st.session_state.vector_store = AssistantPipeline.ensure_vector_store(
                session_dir, st.session_state.vector_store
            )
            status.markdown(render_reasoning(0), unsafe_allow_html=True)

            def on_step(step_idx, _node_name):
                status.markdown(render_reasoning(step_idx), unsafe_allow_html=True)

            answer, metadata = AssistantPipeline.query(
                prompt=task["prompt"],
                messages=st.session_state.messages,
                vector_store=st.session_state.vector_store,
                file_names=st.session_state.uploaded_file_names,
                urls=st.session_state.ingested_urls,
                session_dir=session_dir,
                on_step=on_step,
            )

            status.empty()
            stream_text(answer, metadata, streaming_placeholder)
            st.session_state.messages.append({"role": "assistant", "content": answer, "metadata": metadata})
        elif task.get("files") or task.get("url"):
            status.empty()
            notice = "Your document has been indexed. What would you like to know about it?"
            stream_text(notice, {}, streaming_placeholder)
            st.session_state.messages.append({"role": "assistant", "content": notice, "metadata": {}})
    except Exception as exc:
        status.empty()
        st.session_state.messages.append({"role": "assistant", "content": f"I ran into an error while processing that request: {exc}", "metadata": {}})
    finally:
        st.session_state.processing = None
        _save()
        st.rerun()
