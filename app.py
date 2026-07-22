"""Streamlit interface for the Agentic RAG chatbot."""

import time
import uuid
from datetime import datetime
import textwrap
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from helpers import (
    background_data_url,
    esc,
    human_time,
    render_reasoning,
    render_indexing_status,
    build_assistant_html,
    build_ragas_badges,
    extract_url_from_prompt,
    format_file_size,
    session_path,
    load_session,
    save_session as persist_session,
    delete_session,
    conversation_history,
    check_rate_limit,
    reset_rate_limit,
)
from rag_engine import process_uploaded_files, process_url
from rag_agent import run_agent_pipeline


def _save() -> None:
    persist_session(
        st.session_state.session_id,
        st.session_state.messages,
        st.session_state.uploaded_file_names,
        st.session_state.ingested_urls,
        st.session_state.chunk_count,
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

bg_url = background_data_url()
st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

* {{ box-sizing: border-box; }}
html, body, [class*="css"] {{ font-family: Inter, sans-serif; }}
#MainMenu, footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ visibility: visible; background: transparent!important; }}
header[data-testid="stHeader"] [data-testid="stToolbar"] {{ visibility: hidden; }}
button[data-testid="stSidebarCollapseButton"], button[data-testid="stSidebarCollapsedControl"],
button[data-testid="stBaseButton-headerNoPadding"],
button[data-testid="stExpandSidebarButton"] {{
  visibility:visible!important; opacity:1!important; display:flex!important; position:fixed!important; top:14px; left:14px;
  width:38px!important; height:38px!important; border:1px solid rgba(255,115,0,.55)!important;
  border-radius:11px!important; background:rgba(8,8,8,.82)!important; color:#ff7a00!important;
  box-shadow:0 0 18px rgba(255,100,0,.16); z-index:1000000!important;
}}
button[data-testid="stSidebarCollapseButton"] svg, button[data-testid="stSidebarCollapsedControl"] svg,
button[data-testid="stBaseButton-headerNoPadding"] svg,
button[data-testid="stExpandSidebarButton"] svg {{ color:#ff7a00!important; fill:currentColor!important; }}
header button[data-testid="stBaseButton-header"] {{ visibility:hidden!important; pointer-events:none!important; }}
.stApp {{
  background: #050505 url('{bg_url}') center/cover fixed no-repeat;
  color: #f5f5f5;
}}
.stApp::before {{
  content: ""; position: fixed; inset: 0; pointer-events: none;
  background: radial-gradient(circle at 76% 7%, rgba(255,101,0,.06), transparent 26%),
              radial-gradient(circle at 12% 90%, rgba(255,90,0,.05), transparent 28%);
  z-index: 0;
}}
[data-testid="stAppViewContainer"] > .main {{ position: relative; z-index: 1; }}
[data-testid="stMainBlockContainer"] {{ max-width: 1120px; padding: 20px 38px 132px; }}

section[data-testid="stSidebar"] {{
  background: rgba(7,7,7,.78); border-right: 1px solid rgba(255,255,255,.10);
  backdrop-filter: blur(22px);
  position: relative !important;
}}
section[data-testid="stSidebar"] [data-testid="element-container"],
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"],
section[data-testid="stSidebar"] .stHtml,
section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {{
  position: static !important;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
  padding-bottom: 80px !important;
}}
.brand {{ display:flex; align-items:center; gap:12px; padding:12px 4px 24px; }}
.brand-mark {{ width:48px; height:48px; display:grid; place-items:center; border:1px solid #f97316;
  border-radius:16px; color:#ff7a00; font-size:23px; box-shadow:0 0 22px rgba(249,115,22,.23); }}
.brand-name {{ color:#f7f7f7; font-size:20px; font-weight:700; letter-spacing:-.6px; }}
.brand-subtitle {{ color:#ff7410; font-size:15px; margin-top:3px; }}

section[data-testid="stSidebar"] .stButton > button {{
  width:100%; height:50px; border:0; border-radius:10px; color:#fff; font-weight:600; font-size:15px;
  background:linear-gradient(105deg,#ff4d00,#ff7a00); box-shadow:0 8px 24px rgba(255,80,0,.32);
  transition:transform 220ms ease, box-shadow 220ms ease;
}}
section[data-testid="stSidebar"] .stButton > button:hover {{ transform:translateY(-2px); box-shadow:0 12px 30px rgba(255,80,0,.48); }}
section[data-testid="stSidebar"] .stButton > button:active {{ transform:scale(.98); }}
/* Chat history custom card */
.chat-history-list {{ display: flex; flex-direction: column; gap: 6px; margin: 4px 0; }}
.chat-card {{
  position: relative;
  border: 1px solid rgba(255,255,255,.06);
  border-radius: 10px;
  background: rgba(255,255,255,.02);
  padding: 10px 36px 10px 12px;
  cursor: pointer;
  transition: background .2s, border-color .2s, box-shadow .2s;
  overflow: hidden;
  min-height: 42px;
  display: flex;
  align-items: center;
}}
.chat-card:hover {{
  background: rgba(255,255,255,.06);
  border-color: rgba(255,255,255,.12);
  box-shadow: 0 2px 12px rgba(0,0,0,.15);
}}
.chat-card.active {{
  border-color: rgba(255,115,0,.5);
  background: rgba(255,87,0,.1);
  border-left: 3px solid #ff6700;
  padding-left: 9px;
  box-shadow: inset 0 0 20px rgba(255,87,0,.04);
}}
.chat-card.active::after {{
  content: '';
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: linear-gradient(to bottom, transparent, #ff6700, transparent);
  opacity: .5;
}}
.chat-card-content {{
  display: flex;
  flex-direction: row;
  align-items: baseline;
  gap: 8px;
  width: 100%;
  min-width: 0;
  overflow: hidden;
}}
.chat-title {{
  color: #a1a1aa;
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
  min-width: 0;
}}
.chat-card.active .chat-title {{ color: #f4f4f5; }}
.chat-time {{
  color: #71717a;
  font-size: 11px;
  white-space: nowrap;
  flex-shrink: 0;
}}
.chat-delete {{
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #a1a1aa;
  font-size: 13px;
  opacity: 0;
  border-radius: 6px;
  transition: opacity .15s, background .15s, color .15s;
  z-index: 10;
  background: rgba(255,255,255,.03);
}}
.chat-card:hover .chat-delete {{ opacity: 1; }}
.chat-delete:hover {{ color: #ef4444; background: rgba(239,68,68,.12); }}

[data-testid="stTextInput"] {{ margin:23px 0 0; }}
[data-testid="stTextInput"] input {{ background:rgba(255,255,255,.025)!important; border:1px solid rgba(255,255,255,.13)!important;
  border-radius:10px!important; color:#f3f3f3!important; height:48px!important; font-size:13px!important; }}
.side-heading {{ color:#a1a1aa; font-size:13px; margin:25px 0 12px 2px; }}
.empty-history {{ color:#71717a; padding:12px 4px; font-size:12px; }}
.chat-history-list {{ display:flex; flex-direction:column; gap:6px; }}
.profile {{
  position: sticky;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  margin: 12px 0 0;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(12, 12, 12, 0.9);
  backdrop-filter: blur(15px);
  color: #f4f4f5;
  font-size: 14px;
  z-index: 99;
  flex-shrink: 0;
}}
.profile-avatar {{ width:40px; height:40px; display:grid; place-items:center; border-radius:50%; border:1px solid #f97316; color:#fff; font-weight:600; background:rgba(249,115,22,0.1); }}

.hero {{ text-align:center; margin:0 auto 10px; }}
.hero h1 {{ margin:0; font-size:38px; letter-spacing:-1.6px; color:#f6f6f6!important; }}
.hero h1 span {{ color:#ff6a00!important; }}
.hero p {{ margin:9px 0 20px; color:#d4d4d8; font-size:16px; }}
.badges {{ display:flex; flex-wrap:wrap; justify-content:center; gap:12px; }}
.badge {{ padding:12px 25px; border:1px solid rgba(255,255,255,.12); border-radius:16px; background:rgba(255,255,255,.035);
  box-shadow:0 10px 25px rgba(0,0,0,.16); color:#e4e4e7; font-size:13px; }}
.badge i {{ color:#ff7400; font-style:normal; margin-right:8px; }}
.conversation {{ max-width:980px; margin:12px auto 0; }}
.message-user {{ display:flex; justify-content:flex-end; margin:12px 0; animation:rise 300ms ease both; }}
.user-bubble {{ width:fit-content; max-width:590px; min-width:0; padding:12px 16px; border:1px solid rgba(255,255,255,.12); border-radius:16px;
  background:rgba(255,255,255,.05); backdrop-filter:blur(16px); box-shadow:0 10px 30px rgba(0,0,0,.22); }}
.user-header {{ display:flex; align-items:center; justify-content:flex-end; gap:8px; color:#ff7a00; font-size:13px; font-weight:600; }}
.user-avatar {{ width:34px; height:34px; display:grid; place-items:center; border-radius:50%; border:1px solid #ff7300; color:#ff7300; font-size:16px; }}
.user-content {{ color:#f4f4f5; margin-top:6px; line-height:1.45; }}
.timestamp {{ text-align:right; color:#a1a1aa; font-size:11px; margin-top:5px; }}
.file-card {{ display:inline-flex; align-items:center; gap:9px; min-width:205px; max-width:100%; padding:8px 12px; margin:5px 5px 0 0;
  border:1px solid rgba(255,115,0,.2); border-radius:12px; background:rgba(255,100,0,.06); animation:rise 300ms ease both; }}
.file-icon {{ width:36px; height:36px; display:grid; place-items:center; border-radius:8px; font-size:18px; }}
.file-icon.pdf {{ background:rgba(239,68,68,.15); color:#ef4444; }}
.file-icon.url {{ background:rgba(59,130,246,.15); color:#3b82f6; }}
.file-icon.md {{ background:rgba(34,197,94,.15); color:#22c55e; }}
.file-icon.csv {{ background:rgba(168,85,247,.15); color:#a855f7; }}
.file-icon.default {{ background:rgba(255,255,255,.08); color:#a1a1aa; }}
.file-name {{ font-size:13px; font-weight:600; color:#f4f4f5; }}
.file-meta {{ color:#a1a1aa; font-size:11px; margin-top:2px; }} .file-check {{ margin-left:auto; color:#22c55e; font-size:16px; }}

.reasoning {{
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 14px 0;
  padding: 12px 18px;
  border: 1px solid rgba(255,255,255,.11);
  border-radius: 17px;
  background: rgba(255,255,255,.03);
  overflow-x: auto;
  white-space: nowrap;
}}
.reasoning-title {{
  color: #ff7a00;
  font-weight: 700;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}}
.reasoning-step {{
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: color 0.3s, opacity 0.3s;
}}
.reasoning-step.completed {{
  color: #f59e0b;
  opacity: 0.85;
}}
.reasoning-step.active {{
  color: #ff7a00;
  font-weight: 600;
  opacity: 1;
  animation: pulse-glow 1.5s infinite ease-in-out;
}}
.reasoning-step.pending {{
  color: #52525b;
  opacity: 0.5;
}}
@keyframes pulse-glow {{
  0%, 100% {{ opacity: 0.7; }}
  50% {{ opacity: 1; text-shadow: 0 0 8px rgba(255,122,0,0.4); }}
}}

.trace-panel {{ border:1px solid rgba(255,255,255,.08); border-radius:12px; background:rgba(255,255,255,.02); padding:14px; margin:8px 0; }}
.trace-title {{ font-size:13px; font-weight:600; color:#ff7a00; margin-bottom:10px; display:flex; align-items:center; gap:6px; }}
.trace-row {{ display:flex; justify-content:space-between; align-items:center; padding:5px 0; border-bottom:1px solid rgba(255,255,255,.04); font-size:12px; }}
.trace-row:last-child {{ border-bottom:none; }}
.trace-label {{ color:#a1a1aa; }}
.trace-value {{ color:#f4f4f5; font-weight:500; }}
.trace-step {{ display:flex; align-items:center; gap:8px; padding:4px 0; font-size:12px; }}
.trace-dot {{ width:8px; height:8px; border-radius:50%; flex-shrink:0; }}
.trace-dot.done {{ background:#22c55e; }}
.trace-dot.running {{ background:#ff7a00; animation:pulse-glow 1.5s infinite; }}
.trace-dot.pending {{ background:#3f3f46; }}
.trace-step-name {{ color:#d4d4d8; flex:1; }}
.trace-step-ms {{ color:#71717a; font-size:11px; }}
.trace-ctx {{ font-size:11px; color:#71717a; background:rgba(255,255,255,.03); border-radius:8px; padding:8px 10px; margin-top:8px; max-height:80px; overflow-y:auto; line-height:1.4; word-break:break-word; }}
.trace-link {{ display:inline-block; margin-top:8px; font-size:11px; color:#3b82f6; text-decoration:none; }}
.trace-link:hover {{ text-decoration:underline; }}

.message-assistant {{ max-width:80%; display:flex; gap:12px; align-items:flex-start; margin:14px 0 18px; animation:rise 300ms ease both; }}
.assistant-avatar {{ width:48px; min-width:48px; height:48px; display:grid; place-items:center; border:1px solid rgba(255,115,0,.45); border-radius:50%;
  color:#ff7200; font-size:22px; background:rgba(255,100,0,.06); box-shadow:0 0 14px rgba(255,100,0,.12); }}
.assistant-card {{ width:100%; padding:16px 20px; border:1px solid rgba(255,255,255,.12); border-radius:18px;
  background:rgba(255,255,255,.04); backdrop-filter:blur(20px); box-shadow:0 14px 32px rgba(0,0,0,.27); color:#f5f5f5; line-height:1.65; }}
.assistant-card h1,.assistant-card h2,.assistant-card h3,.assistant-card h4 {{ color:#ff7a00!important; font-size:16px!important; font-weight:700!important; margin-top:18px!important; margin-bottom:6px!important; }}
.assistant-card p {{ color:#e4e4e7!important; }}
.assistant-card strong {{ color:#ff7a00!important; font-weight:600!important; }}
.assistant-card pre {{ background:#090909!important; border:1px solid rgba(255,255,255,.11)!important; border-radius:12px!important; padding:13px!important; overflow:auto!important; }}
.assistant-card code {{ color:#fdba74!important; }}
.assistant-card ul,.assistant-card ol {{ padding-left:20px!important; margin:6px 0!important; }}
.assistant-card li {{ color:#d4d4d8!important; margin:3px 0!important; }}
.assistant-card li strong {{ color:#ff7a00!important; }}
.metadata {{ display:flex; flex-wrap:wrap; gap:9px; margin-top:14px; }}
.metadata span {{ padding:7px 14px; border:1px solid rgba(255,115,0,.25); border-radius:999px; color:#d4d4d8; font-size:12px; background:rgba(255,115,0,.06); }}
.metadata b {{ color:#ff7a00; }}
.citations {{ display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin-top:14px; padding-top:12px; border-top:1px solid rgba(255,255,255,.07); }}
.citations-label {{ color:#a1a1aa; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.08em; margin-right:2px; }}
.citation-chip {{
  display:inline-flex; align-items:center; gap:6px; padding:5px 12px 5px 5px;
  border:1px solid rgba(255,115,0,.28); border-radius:999px;
  background:linear-gradient(135deg, rgba(255,115,0,.10), rgba(255,0,123,.06));
  font-size:12px; color:#e4e4e7; transition:all .2s ease; cursor:default;
}}
.citation-chip:hover {{ border-color:rgba(255,115,0,.6); background:linear-gradient(135deg, rgba(255,115,0,.18), rgba(255,0,123,.10)); box-shadow:0 0 12px rgba(255,115,0,.25); }}
.citation-num {{
  display:inline-flex; align-items:center; justify-content:center;
  width:18px; height:18px; border-radius:50%; flex-shrink:0;
  background:linear-gradient(135deg,#ff5a00,#ff8a00); color:#fff;
  font-size:10px; font-weight:700;
}}
.citation-icon {{ font-size:12px; }}
.citation-name {{ color:#e4e4e7; max-width:260px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.citation-page {{ color:#ff9a3c; font-size:11px; font-weight:600; padding-left:6px; border-left:1px solid rgba(255,115,0,.3); }}
.ragas-scores {{ margin-top:8px!important; }}
.ragas-badge {{ padding:6px 14px!important; border:1px solid; border-radius:999px; font-size:12px; display:inline-flex; align-items:center; gap:4px; }}
.ragas-badge b {{ font-size:13px; }}
div[data-testid="stButton"] > button {{ background:rgba(255,115,0,.1)!important; border:1px solid rgba(255,115,0,.3)!important; border-radius:999px!important; color:#d4d4d8!important; font-size:12px!important; padding:4px 14px!important; transition:all .2s ease!important; }}
div[data-testid="stButton"] > button:hover {{ background:rgba(255,115,0,.2)!important; border-color:rgba(255,115,0,.5)!important; color:#fff!important; }}
[data-testid="stBottom"], [data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"],
[data-testid="stBottomBlockContainer"] > div {{
  background:transparent!important; box-shadow:none!important;
}}
[data-testid="stBottomBlockContainer"] {{ padding:16px 24px 24px!important; }}

[data-testid="stChatInput"] {{
  position: relative!important;
  max-width: 980px;
  margin: 0 auto !important;
  border: none !important;
  border-radius: 16px !important;
  background: rgba(15,15,15,.85) !important;
  animation: neon-pulse 2.5s infinite ease-in-out;
  transition: box-shadow 0.3s ease, border-radius 0.2s ease !important;
  overflow: hidden;
}}
@keyframes neon-pulse {{
  0%, 100% {{
    box-shadow: 0 0 8px rgba(255,77,0,.45), 0 0 18px rgba(255,138,0,.28),
                0 0 34px rgba(255,0,123,.16), 0 4px 20px rgba(0,0,0,.4);
  }}
  50% {{
    box-shadow: 0 0 14px rgba(255,77,0,.7), 0 0 30px rgba(255,138,0,.45),
                0 0 55px rgba(255,0,123,.28), 0 4px 20px rgba(0,0,0,.4);
  }}
}}
@keyframes neon-pulse-focus {{
  0%, 100% {{
    box-shadow: 0 0 16px rgba(255,77,0,.85), 0 0 36px rgba(255,138,0,.55),
                0 0 70px rgba(255,0,123,.35), 0 4px 20px rgba(0,0,0,.4);
  }}
  50% {{
    box-shadow: 0 0 24px rgba(255,77,0,1), 0 0 55px rgba(255,138,0,.75),
                0 0 95px rgba(255,0,123,.5), 0 4px 20px rgba(0,0,0,.4);
  }}
}}
[data-testid="stChatInput"]::before {{
  content: "";
  position: absolute;
  inset: 0;
  border-radius: 16px;
  padding: 1.5px;
  background: linear-gradient(135deg, #ff4d00, #ff8a00, #00f0ff, #ff007b, #ff4d00);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  background-size: 300% 300%;
  animation: gradient-border 6s linear infinite;
  pointer-events: none;
}}
[data-testid="stChatInput"]:focus-within::before {{
  animation: gradient-border-focus 3s linear infinite;
  filter: brightness(1.3);
}}
[data-testid="stChatInput"]:focus-within {{
  animation: neon-pulse-focus 1.8s infinite ease-in-out;
}}
@keyframes gradient-border {{
  0% {{ background-position: 0% 50%; }}
  50% {{ background-position: 100% 50%; }}
  100% {{ background-position: 0% 50%; }}
}}
@keyframes gradient-border-focus {{
  0% {{ background-position: 0% 50%; }}
  50% {{ background-position: 100% 50%; }}
  100% {{ background-position: 0% 50%; }}
}}

[data-testid="stChatInput"] > div, [data-testid="stChatInput"] [data-baseweb="textarea"],
[data-testid="stChatInput"] textarea, [data-testid="stChatInput"] [data-baseweb="input"] {{
  background:transparent!important; border:none!important; box-shadow:none!important; outline:none!important;
}}
[data-testid="stChatInput"] textarea {{ color:#f4f4f5!important; }}
[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"] {{ background:linear-gradient(135deg,#ff5a00,#ff8a00)!important; border-radius:50%!important; color:white!important; }}
[data-testid="stChatInput"] [data-testid="stChatFileUploadDropzone"] {{
  background: rgba(255,255,255,.04)!important; border:1px dashed rgba(255,115,0,.3)!important; border-radius:12px!important;
}}
[data-testid="stChatInput"] [data-testid="stChatFileUpload"] {{ display:none!important; }}
a.anchor-link {{ display: none !important; visibility: hidden !important; }}
@keyframes rise {{ from {{ opacity:0; transform:translateY(12px); }} to {{ opacity:1; transform:translateY(0); }} }}
/* Delete confirmation dialog */
[role="dialog"] {{
  background:rgba(15,15,15,.98)!important; border:1px solid rgba(255,115,0,.15)!important;
  border-radius:16px!important; box-shadow:0 25px 60px rgba(0,0,0,.6), 0 0 40px rgba(255,100,0,.08)!important;
  color:#f4f4f5!important; max-width:420px!important;
}}
[role="dialog"] header {{ border-bottom:1px solid rgba(255,255,255,.08)!important; }}
[role="dialog"] header span {{ color:#f4f4f5!important; font-weight:600!important; }}
[role="dialog"] button[aria-label="Close"] {{ color:#a1a1aa!important; }}
[role="dialog"] button[aria-label="Close"]:hover {{ color:#f4f4f5!important; }}
[role="dialog"] .stButton > button {{ border-radius:10px!important; height:42px!important; font-weight:600!important; font-size:14px!important; background-image:none!important; }}
[role="dialog"] .stButton > button[kind="primary"] {{
  background:linear-gradient(135deg,#dc2626,#ef4444)!important; border:none!important; color:#fff!important;
  box-shadow:0 4px 14px rgba(239,68,68,.3)!important;
}}
[role="dialog"] .stButton > button[kind="primary"]:hover {{
  box-shadow:0 8px 24px rgba(239,68,68,.5)!important; transform:translateY(-1px)!important;
}}
@media (max-width: 850px) {{ .hero h1 {{ font-size:30px; }} .assistant-avatar {{ width:45px; min-width:45px; height:45px; border-radius:14px; }} .profile {{ position:static; margin-top:28px; }} }}
</style>
""",
    unsafe_allow_html=True,
)

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


if "session_id" not in st.query_params:
    st.query_params["session_id"] = str(uuid.uuid4())
    st.rerun()

session_id = str(st.query_params["session_id"])
saved = load_session(session_id)
if st.session_state.get("loaded_session") != session_id:
    st.session_state.loaded_session = session_id
    st.session_state.session_id = session_id
    st.session_state.messages = saved.get("messages", [])
    st.session_state.uploaded_file_names = saved.get("uploaded_file_names", [])
    st.session_state.ingested_urls = saved.get("ingested_urls", [])
    st.session_state.chunk_count = saved.get("chunk_count", 0)
    st.session_state.vector_store = None
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
        '<div class="brand"><div class="brand-mark">\u2727</div><div><div class="brand-name">Agentic RAG</div><div class="brand-subtitle">Chatbot</div></div></div>',
        unsafe_allow_html=True,
    )
    st.button("\uff0b  New Chat", on_click=new_chat, use_container_width=True)
    search_term = st.text_input("Search conversations", placeholder="\u2315  Search conversations...", label_visibility="collapsed")
    st.markdown('<div class="side-heading">Recent Chats</div>', unsafe_allow_html=True)
    matching_history = [
        item for item in conversation_history()
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

    st.markdown('<div class="profile"><div class="profile-avatar">MB</div><div><div style="font-size:13px;font-weight:600;">Muhammad Bilal</div><div style="font-size:11px;color:#71717a;">mbilal@example.com</div></div></div>', unsafe_allow_html=True)


# Delete confirmation modal (overlay at top of screen)
if st.session_state.get("delete_confirm"):
    show_delete_dialog()


document_count = len(st.session_state.uploaded_file_names) + len(st.session_state.ingested_urls)
document_label = f"{document_count} Document{'s' if document_count != 1 else ''}"
chunk_count = st.session_state.get("chunk_count", 0)
chunk_badge = f'<span class="badge"><i>◫</i>{chunk_count:,} Chunks</span>' if chunk_count else ""
st.markdown(
    f"""
    <div class="hero">
      <h1>Agentic <span>RAG</span> Chatbot</h1>
      <p>Your AI research assistant, powered by retrieval and reasoning.</p>
      <div class="badges"><span class="badge"><i>♢</i>Guardrails Enabled</span><span class="badge"><i>♙</i>Agent Mode</span><span class="badge"><i>▧</i>{document_label}</span>{chunk_badge}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

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
                from agent import evaluate_ragas
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
    import asyncio

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
        if task.get("files") or task.get("url"):
            if task.get("files"):
                status.markdown(render_indexing_status("Reading uploaded files..."), unsafe_allow_html=True)
                store, count = asyncio.run(process_uploaded_files(
                    task["files"],
                    existing_store=st.session_state.vector_store,
                    persist_directory=str(session_path(st.session_state.session_id) / "qdrant_db"),
                    progress_callback=indexing_progress,
                ))
                if count:
                    st.session_state.vector_store = store
                    st.session_state.chunk_count += count
                    st.session_state.uploaded_file_names.extend(file.name for file in task["files"])
            if task.get("url"):
                status.markdown(render_indexing_status(f"Fetching and scraping web page: {task['url']}"), unsafe_allow_html=True)
                store, count = asyncio.run(process_url(
                    task["url"], st.session_state.vector_store,
                    persist_directory=str(session_path(st.session_state.session_id) / "qdrant_db"),
                    progress_callback=indexing_progress,
                ))
                if count:
                    st.session_state.vector_store = store
                    st.session_state.chunk_count += count
                    st.session_state.ingested_urls.append(task["url"])
        if task.get("prompt"):
            status.markdown(render_reasoning(0), unsafe_allow_html=True)
            history = [
                {
                    "role": message["role"],
                    "content": message["content"],
                    "files": message.get("files", []),
                }
                for message in st.session_state.messages[:-1]
                if message.get("role") in {"user", "assistant"}
            ]
            history.append({
                "role": "user",
                "content": task["prompt"],
                "files": st.session_state.messages[-1].get("files", []) if st.session_state.messages else [],
            })

            def on_step(step_idx, _node_name):
                status.markdown(render_reasoning(step_idx), unsafe_allow_html=True)

            answer, metadata = asyncio.run(run_agent_pipeline(
                st.session_state.vector_store,
                history,
                st.session_state.uploaded_file_names,
                st.session_state.ingested_urls,
                session_dir=str(session_path(st.session_state.session_id)),
                on_step=on_step,
            ))

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
