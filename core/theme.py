"""Obsidian Ember Luxury Theme Engine.

Adhering to: design-motion-principles, high-end-visual-design,
awesome-claude-design, refactoring-ui, ui-ux-pro-max.
"""

import logging
from typing import Optional

logger = logging.getLogger("theme")

THEME_CSS_TEMPLATE = """/* ==========================================================================
   AGENTIC RAG — HIGH-END LUXURY DESIGN SYSTEM (OBSIDIAN EMBER)
   Adhering to: design-motion-principles, high-end-visual-design,
                awesome-claude-design, refactoring-ui, ui-ux-pro-max
   ========================================================================== */

@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,300..800;1,300..800&family=Bebas+Neue&family=Inter:wght@300;400;500;600;700;800&family=Space+Mono:ital,wght@0,400;0,700;1,400&display=swap');

/* Bebas Neue - latin-ext */
@font-face {
  font-family: 'Bebas Neue';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url(https://fonts.gstatic.com/s/bebasneue/v16/JTUSjIg69CK48gW7PXoo9Wdhyzbi.woff2) format('woff2');
  unicode-range: U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF;
}
/* Bebas Neue - latin */
@font-face {
  font-family: 'Bebas Neue';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url(https://fonts.gstatic.com/s/bebasneue/v16/JTUSjIg69CK48gW7PXoo9Wlhyw.woff2) format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}

/* Inter - cyrillic-ext (400) */
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url(https://fonts.gstatic.com/s/inter/v20/UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa2JL7SUc.woff2) format('woff2');
  unicode-range: U+0460-052F, U+1C80-1C8A, U+20B4, U+2DE0-2DFF, U+A640-A69F, U+FE2E-FE2F;
}
/* Inter - cyrillic (400) */
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url(https://fonts.gstatic.com/s/inter/v20/UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa0ZL7SUc.woff2) format('woff2');
  unicode-range: U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116;
}
/* Inter - latin (400) */
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url(https://fonts.gstatic.com/s/inter/v20/UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7.woff2) format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}
/* Inter - latin (700) */
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-weight: 700;
  font-display: swap;
  src: url(https://fonts.gstatic.com/s/inter/v20/UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7.woff2) format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}

/* Space Mono - latin (400) */
@font-face {
  font-family: 'Space Mono';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url(https://fonts.gstatic.com/s/spacemono/v17/i7dPIFZifjKcF5UAWdDRYEF8RQ.woff2) format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}

/* --------------------------------------------------------------------------
   DESIGN TOKENS & ATOMIC VARIABLES
   -------------------------------------------------------------------------- */
:root {
  /* Typographic Stacks */
  --font-sans: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-display: 'Bebas Neue', var(--font-sans);
  --font-mono: 'Space Mono', 'JetBrains Mono', 'Fira Code', monospace;

  /* Motion & Physics Curves (Emil Kowalski & Jakub Krehel) */
  --ease-spring: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
  --ease-smooth: cubic-bezier(0.32, 0.72, 0, 1);
  --ease-snappy: cubic-bezier(0.2, 0.8, 0.2, 1);
  --ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);

  --duration-instant: 110ms;
  --duration-fast: 180ms;
  --duration-normal: 260ms;
  --duration-smooth: 360ms;
  --duration-ambient: 4000ms;

  /* Obsidian Ember Surface Hierarchy */
  --bg-canvas: #06070a;
  --bg-surface-glass: rgba(11, 13, 19, 0.78);
  --bg-surface-elevated: rgba(16, 18, 26, 0.88);
  --bg-surface-card: rgba(14, 16, 24, 0.72);
  --bg-surface-core: rgba(10, 12, 18, 0.92);

  /* Doppelrand (Double-Bezel) Architecture Tokens */
  --bezel-outer-border: rgba(255, 255, 255, 0.08);
  --bezel-outer-bg: rgba(255, 255, 255, 0.02);
  --bezel-inner-highlight: inset 0 1px 1px rgba(255, 255, 255, 0.14), inset 0 0 0 1px rgba(255, 255, 255, 0.02);
  --bezel-shadow-ambient: 0 16px 42px rgba(0, 0, 0, 0.5);

  /* Electric Ember & Amber Accent System */
  --brand-orange: #ff6700;
  --brand-orange-bright: #ff7d00;
  --brand-orange-light: #ffa338;
  --brand-orange-dark: #e05500;
  --brand-orange-glow: rgba(255, 103, 0, 0.32);
  --brand-orange-subtle: rgba(255, 103, 0, 0.08);
  --brand-orange-border: rgba(255, 103, 0, 0.38);

  /* Semantic Highlights */
  --color-emerald: #10b981;
  --color-emerald-glow: rgba(16, 185, 129, 0.28);
  --color-ruby: #ef4444;
  --color-ruby-glow: rgba(239, 68, 68, 0.25);
  --color-cyan: #06b6d4;

  /* Typography Colors */
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --text-dim: #475569;

  /* Focus Ring */
  --focus-ring: 0 0 0 3px rgba(255, 103, 0, 0.22), 0 0 24px rgba(255, 103, 0, 0.18);
}

/* --------------------------------------------------------------------------
   GLOBAL RESET & TYPOGRAPHIC BASE
   -------------------------------------------------------------------------- */
* {
  box-sizing: border-box;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

html, body, [class*="css"] {
  font-family: var(--font-sans);
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

h1, h2, h3, h4, .brand-name, .hero h1, .auth-title {
  font-family: var(--font-display) !important;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

code, pre, .trace-step-ms, .timestamp, .citation-num, .telemetry-pill {
  font-family: var(--font-mono) !important;
}

/* Hide default Streamlit clutter cleanly */
#MainMenu, footer { visibility: hidden !important; }
header[data-testid="stHeader"] { visibility: visible; background: transparent !important; }
header[data-testid="stHeader"] [data-testid="stToolbar"] { visibility: hidden !important; }
header button[data-testid="stBaseButton-header"] { visibility: hidden !important; pointer-events: none !important; }

/* --------------------------------------------------------------------------
   SIDEBAR TOGGLE BUTTON (TACTILE GLASS CHIP)
   -------------------------------------------------------------------------- */
button[data-testid="stSidebarCollapseButton"],
button[data-testid="stSidebarCollapsedControl"],
button[data-testid="stBaseButton-headerNoPadding"],
button[data-testid="stExpandSidebarButton"] {
  visibility: visible !important;
  opacity: 1 !important;
  display: flex !important;
  position: fixed !important;
  top: 14px;
  left: 14px;
  width: 40px !important;
  height: 40px !important;
  border: 1px solid var(--brand-orange-border) !important;
  border-radius: 12px !important;
  background: rgba(10, 12, 17, 0.88) !important;
  backdrop-filter: blur(16px) !important;
  color: var(--brand-orange) !important;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.5), inset 0 1px 1px rgba(255, 255, 255, 0.12), 0 0 16px rgba(255, 103, 0, 0.15) !important;
  z-index: 1000000 !important;
  transition: transform var(--duration-fast) var(--ease-spring), box-shadow var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out) !important;
}

@media (hover: hover) and (pointer: fine) {
  button[data-testid="stSidebarCollapseButton"]:hover,
  button[data-testid="stSidebarCollapsedControl"]:hover,
  button[data-testid="stBaseButton-headerNoPadding"]:hover,
  button[data-testid="stExpandSidebarButton"]:hover {
    transform: translateY(-2px) scale(1.02) !important;
    border-color: var(--brand-orange-bright) !important;
    box-shadow: 0 8px 26px rgba(0, 0, 0, 0.6), inset 0 1px 1px rgba(255, 255, 255, 0.2), 0 0 24px rgba(255, 103, 0, 0.35) !important;
  }
}

button[data-testid="stSidebarCollapseButton"]:active,
button[data-testid="stSidebarCollapsedControl"]:active,
button[data-testid="stBaseButton-headerNoPadding"]:active,
button[data-testid="stExpandSidebarButton"]:active {
  transform: scale(0.96) !important;
}

button[data-testid="stSidebarCollapseButton"] svg,
button[data-testid="stSidebarCollapsedControl"] svg,
button[data-testid="stBaseButton-headerNoPadding"] svg,
button[data-testid="stExpandSidebarButton"] svg {
  color: var(--brand-orange) !important;
  fill: currentColor !important;
}

/* --------------------------------------------------------------------------
   ATMOSPHERIC CANVASES & MESH LIGHTING
   -------------------------------------------------------------------------- */
.stApp {
  background: #050608 url('{bg_url}') center/cover fixed no-repeat;
  color: var(--text-primary);
  min-height: 100vh;
}

.stApp::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(ellipse 70% 50% at 80% 5%, rgba(255, 103, 0, 0.08), transparent 70%),
    radial-gradient(ellipse 60% 45% at 15% 95%, rgba(30, 42, 80, 0.12), transparent 70%),
    radial-gradient(circle at 50% 50%, rgba(255, 103, 0, 0.02), transparent 80%);
  z-index: 0;
}

[data-testid="stAppViewContainer"] > .main {
  position: relative;
  z-index: 1;
}

[data-testid="stMainBlockContainer"] {
  max-width: 1140px;
  padding: 24px 36px 140px;
}

/* --------------------------------------------------------------------------
   SIDEBAR ARCHITECTURE & GLASS
   -------------------------------------------------------------------------- */
section[data-testid="stSidebar"] {
  background: rgba(8, 9, 14, 0.84) !important;
  border-right: 1px solid var(--bezel-outer-border) !important;
  backdrop-filter: blur(32px) !important;
  position: relative !important;
  box-shadow: 10px 0 40px rgba(0, 0, 0, 0.4) !important;
}

section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
  padding-bottom: 96px !important;
}

/* Brand Section with Concentric Squircle Halo */
.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 4px 22px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  margin-bottom: 16px;
}

.brand-mark-outer {
  width: 48px;
  height: 48px;
  border-radius: 16px;
  padding: 2px;
  background: linear-gradient(135deg, rgba(255, 103, 0, 0.4), rgba(255, 255, 255, 0.05));
  box-shadow: 0 4px 20px rgba(255, 103, 0, 0.25);
  display: grid;
  place-items: center;
  transition: transform var(--duration-fast) var(--ease-spring), box-shadow var(--duration-fast) var(--ease-out);
}

.brand-mark {
  width: 100%;
  height: 100%;
  border-radius: 14px;
  background: #0d0f15;
  border: 1px solid rgba(255, 103, 0, 0.3);
  display: grid;
  place-items: center;
  color: var(--brand-orange);
  font-size: 22px;
  box-shadow: inset 0 1px 2px rgba(255, 255, 255, 0.15), 0 0 16px rgba(255, 103, 0, 0.2);
}

.brand:hover .brand-mark-outer {
  transform: scale(1.05) rotate(2deg);
  box-shadow: 0 6px 28px rgba(255, 103, 0, 0.45);
}

.brand-name {
  color: #f8fafc;
  font-size: 26px;
  font-weight: 400;
  letter-spacing: 0.06em;
  line-height: 1;
  text-transform: uppercase;
}

.brand-badge-row {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 4px;
}

.brand-tag {
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--brand-orange-light);
  background: var(--brand-orange-subtle);
  border: 1px solid rgba(255, 103, 0, 0.25);
  padding: 1px 6px;
  border-radius: 5px;
}

.brand-status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--color-emerald);
  box-shadow: 0 0 8px var(--color-emerald);
}

.brand-subtitle {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 500;
}

/* --------------------------------------------------------------------------
   SIDEBAR BUTTONS: BUTTON-IN-BUTTON / ISLAND ARCHITECTURE
   -------------------------------------------------------------------------- */
section[data-testid="stSidebar"] .stButton > button {
  width: 100%;
  height: 48px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 14px;
  color: #ffffff;
  font-family: var(--font-display) !important;
  font-weight: 500;
  font-size: 16px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: linear-gradient(135deg, #e65100 0%, #ff6700 60%, #ff8500 100%);
  box-shadow:
    inset 0 1px 1px rgba(255, 255, 255, 0.35),
    0 4px 18px rgba(255, 103, 0, 0.32),
    0 1px 3px rgba(0, 0, 0, 0.4);
  transition:
    transform var(--duration-fast) var(--ease-spring),
    box-shadow var(--duration-fast) var(--ease-out),
    filter var(--duration-fast) var(--ease-out);
  cursor: pointer;
}

@media (hover: hover) and (pointer: fine) {
  section[data-testid="stSidebar"] .stButton > button:hover {
    transform: translateY(-2px);
    box-shadow:
      inset 0 1px 1px rgba(255, 255, 255, 0.5),
      0 8px 30px rgba(255, 103, 0, 0.5),
      0 2px 6px rgba(0, 0, 0, 0.5);
    filter: brightness(1.04);
  }
}

section[data-testid="stSidebar"] .stButton > button:active {
  transform: scale(0.975);
  box-shadow:
    inset 0 1px 1px rgba(0, 0, 0, 0.2),
    0 2px 8px rgba(255, 103, 0, 0.25);
}

/* Sidebar Search Input (Double-Bezel Shell) */
[data-testid="stSidebar"] [data-testid="stTextInput"] {
  margin: 16px 0 0;
}

[data-testid="stSidebar"] [data-testid="stTextInput"] input {
  background: rgba(13, 15, 22, 0.85) !important;
  border: 1px solid var(--bezel-outer-border) !important;
  border-radius: 12px !important;
  color: #f8fafc !important;
  height: 44px !important;
  font-size: 13.5px !important;
  padding: 0 14px !important;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.3) !important;
  transition: border-color var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out) !important;
}

[data-testid="stSidebar"] [data-testid="stTextInput"] input:focus {
  border-color: var(--brand-orange) !important;
  box-shadow: var(--focus-ring), inset 0 1px 2px rgba(0, 0, 0, 0.2) !important;
}

.side-heading {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin: 22px 0 10px 2px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.side-heading::after {
  content: "";
  flex: 1;
  height: 1px;
  background: rgba(255, 255, 255, 0.05);
}

/* --------------------------------------------------------------------------
   CHAT HISTORY CARDS: DOPPELRAND (DOUBLE-BEZEL) SYSTEM
   -------------------------------------------------------------------------- */
.chat-history-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin: 4px 0;
}

.chat-card {
  position: relative;
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.018);
  padding: 2px;
  cursor: pointer;
  transition:
    transform var(--duration-fast) var(--ease-spring),
    border-color var(--duration-fast) var(--ease-out),
    box-shadow var(--duration-fast) var(--ease-out);
}

.chat-card:hover {
  transform: translateX(4px);
  border-color: rgba(255, 255, 255, 0.14);
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.35);
}

.chat-card-content {
  position: relative;
  background: rgba(12, 14, 20, 0.82);
  border-radius: 12px;
  padding: 10px 38px 10px 14px;
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  gap: 3px;
  overflow: hidden;
  transition: background var(--duration-fast) var(--ease-out);
}

.chat-card:hover .chat-card-content {
  background: rgba(16, 19, 28, 0.94);
}

.chat-card.active {
  border-color: var(--brand-orange-border);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.4), 0 0 16px rgba(255, 103, 0, 0.15);
}

.chat-card.active .chat-card-content {
  background: linear-gradient(90deg, rgba(255, 103, 0, 0.12) 0%, rgba(12, 14, 20, 0.88) 100%);
  border-left: 3px solid var(--brand-orange);
  padding-left: 12px;
}

.chat-title {
  color: #e2e8f0;
  font-size: 13.5px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.35;
}

.chat-card.active .chat-title {
  color: #ffffff;
  font-weight: 600;
}

.chat-time {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10.5px;
  white-space: nowrap;
}

.chat-delete {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 13px;
  opacity: 0;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  transition:
    opacity var(--duration-fast) var(--ease-out),
    transform var(--duration-fast) var(--ease-spring),
    background var(--duration-fast) var(--ease-out),
    color var(--duration-fast) var(--ease-out);
  z-index: 10;
}

.chat-card:hover .chat-delete {
  opacity: 1;
}

.chat-delete:hover {
  color: var(--color-ruby);
  background: rgba(239, 68, 68, 0.18);
  border-color: rgba(239, 68, 68, 0.4);
  transform: translateY(-50%) scale(1.1);
}

.empty-history {
  color: var(--text-muted);
  padding: 16px 8px;
  font-size: 13px;
  font-style: italic;
}

/* --------------------------------------------------------------------------
   HERO / WELCOME BANNER (EDITORIAL & POWERFUL)
   -------------------------------------------------------------------------- */
.hero {
  text-align: center;
  margin: 12px auto 20px;
  max-width: 860px;
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 14px;
  border-radius: 999px;
  border: 1px solid var(--brand-orange-border);
  background: var(--brand-orange-subtle);
  color: var(--brand-orange-light);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 12px;
  box-shadow: 0 0 18px rgba(255, 103, 0, 0.12);
}

.hero-pulse {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--brand-orange);
  box-shadow: 0 0 8px var(--brand-orange);
  animation: hero-beacon 2s infinite var(--ease-in-out);
}

@keyframes hero-beacon {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.8); }
}

.hero h1 {
  margin: 0;
  font-size: 58px;
  font-weight: 400;
  letter-spacing: 0.05em;
  color: #ffffff !important;
  line-height: 1.05;
  text-transform: uppercase;
  text-shadow: 0 4px 24px rgba(0, 0, 0, 0.6);
}

.hero h1 span {
  background: linear-gradient(135deg, #ff6700 0%, #ff8500 50%, #ffa338 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  filter: drop-shadow(0 0 20px rgba(255, 103, 0, 0.3));
}

.hero p {
  margin: 10px auto 24px;
  color: var(--text-secondary);
  font-size: 16px;
  line-height: 1.55;
  max-width: 640px;
}

/* Hero Badge Ribbon (Concentric Squircle Pills) */
.badges {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 18px;
  border: 1px solid var(--bezel-outer-border);
  border-radius: 999px;
  background: rgba(14, 16, 24, 0.72);
  backdrop-filter: blur(16px);
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.08), 0 4px 16px rgba(0, 0, 0, 0.3);
  color: #e2e8f0;
  font-size: 12.5px;
  font-weight: 500;
  transition:
    transform var(--duration-fast) var(--ease-spring),
    border-color var(--duration-fast) var(--ease-out),
    box-shadow var(--duration-fast) var(--ease-out);
}

@media (hover: hover) and (pointer: fine) {
  .badge:hover {
    transform: translateY(-2px);
    border-color: var(--brand-orange-border);
    box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.15), 0 8px 24px rgba(0, 0, 0, 0.4), 0 0 16px rgba(255, 103, 0, 0.2);
    color: #ffffff;
  }
}

.badge i {
  color: var(--brand-orange);
  font-style: normal;
  font-size: 13px;
}

/* --------------------------------------------------------------------------
   CHAT FEED & MESSAGES (DOUBLE-BEZEL & SPRING ENTRANCE)
   -------------------------------------------------------------------------- */
@keyframes message-rise {
  from {
    opacity: 0;
    transform: translateY(14px) scale(0.985);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* User Message */
.message-user {
  display: flex;
  justify-content: flex-end;
  margin: 16px 0;
  animation: message-rise var(--duration-smooth) var(--ease-out) both;
}

.user-bubble {
  max-width: 660px;
  min-width: 0;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.02);
  padding: 2px;
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.35);
}

.user-bubble-inner {
  background: linear-gradient(135deg, rgba(20, 24, 34, 0.95) 0%, rgba(14, 16, 24, 0.9) 100%);
  border-radius: 18px;
  padding: 14px 18px;
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.12);
}

.user-header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  color: var(--brand-orange-light);
  font-size: 13px;
  font-weight: 600;
}

.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--brand-orange-subtle);
  border: 1px solid var(--brand-orange-border);
  color: var(--brand-orange);
  font-size: 14px;
}

.user-content {
  color: #f8fafc;
  margin-top: 8px;
  line-height: 1.6;
  font-size: 15px;
}

.timestamp {
  text-align: right;
  color: var(--text-muted);
  font-size: 11px;
  margin-top: 8px;
}

/* File Attachment Card */
.file-card {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  min-width: 220px;
  max-width: 100%;
  padding: 10px 16px;
  margin: 8px 6px 0 0;
  border: 1px solid var(--brand-orange-border);
  border-radius: 14px;
  background: rgba(255, 103, 0, 0.06);
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.08);
  animation: message-rise var(--duration-normal) var(--ease-spring) both;
}

.file-icon {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  font-size: 19px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.file-icon.pdf { background: rgba(239, 68, 68, 0.16); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); }
.file-icon.url { background: rgba(6, 182, 212, 0.16); color: #06b6d4; border: 1px solid rgba(6, 182, 212, 0.3); }
.file-icon.md { background: rgba(16, 185, 129, 0.16); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }
.file-icon.csv { background: rgba(168, 85, 247, 0.16); color: #a855f7; border: 1px solid rgba(168, 85, 247, 0.3); }
.file-icon.docx { background: rgba(59, 130, 246, 0.16); color: #3b82f6; border: 1px solid rgba(59, 130, 246, 0.3); }
.file-icon.default { background: rgba(255, 255, 255, 0.08); color: #a1a1aa; border: 1px solid rgba(255, 255, 255, 0.12); }

.file-name { font-size: 13.5px; font-weight: 600; color: #f8fafc; }
.file-meta { color: var(--text-muted); font-size: 11px; margin-top: 2px; }
.file-check { margin-left: auto; color: var(--color-emerald); font-size: 16px; }

/* --------------------------------------------------------------------------
   ASSISTANT RESPONSE: DOUBLE-BEZEL CARD & TYPOGRAPHY
   -------------------------------------------------------------------------- */
.message-assistant {
  max-width: 86%;
  display: flex;
  gap: 16px;
  align-items: flex-start;
  margin: 18px 0 24px;
  animation: message-rise var(--duration-smooth) var(--ease-out) both;
}

.assistant-avatar {
  width: 46px;
  min-width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  border: 1px solid var(--brand-orange-border);
  color: var(--brand-orange);
  font-size: 22px;
  background: #0e1017;
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.12), 0 0 20px rgba(255, 103, 0, 0.2);
  flex-shrink: 0;
}

.assistant-card {
  width: 100%;
  padding: 22px 26px;
  border: 1px solid var(--bezel-outer-border);
  border-radius: 20px;
  background: var(--bg-surface-glass);
  backdrop-filter: blur(32px);
  box-shadow: var(--bezel-inner-highlight), var(--bezel-shadow-ambient);
  color: #f1f5f9;
  line-height: 1.72;
  font-size: 15px;
}

.assistant-card h1, .assistant-card h2, .assistant-card h3, .assistant-card h4 {
  color: var(--brand-orange-light) !important;
  font-size: 17px !important;
  font-weight: 700 !important;
  margin-top: 22px !important;
  margin-bottom: 10px !important;
  letter-spacing: -0.01em !important;
  text-transform: none !important;
}

.assistant-card p {
  color: #e2e8f0 !important;
  margin: 8px 0 12px !important;
}

.assistant-card strong {
  color: #ffffff !important;
  font-weight: 600 !important;
}

.assistant-card pre {
  background: #08090d !important;
  border: 1px solid rgba(255, 255, 255, 0.09) !important;
  border-radius: 14px !important;
  padding: 16px 18px !important;
  overflow: auto !important;
  margin: 14px 0 !important;
  box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.4) !important;
}

.assistant-card code {
  color: #fcd34d !important;
  font-family: var(--font-mono) !important;
  font-size: 13.5px !important;
}

.assistant-card ul, .assistant-card ol {
  padding-left: 22px !important;
  margin: 10px 0 !important;
}

.assistant-card li {
  color: #cbd5e1 !important;
  margin: 5px 0 !important;
}

.assistant-card blockquote {
  border-left: 3px solid var(--brand-orange) !important;
  margin: 14px 0 !important;
  padding: 8px 16px !important;
  background: var(--brand-orange-subtle) !important;
  border-radius: 0 10px 10px 0 !important;
  color: #f8fafc !important;
}

/* --------------------------------------------------------------------------
   REASONING RIBBON & INGESTION STATUS (HIGH-TECH PULSE)
   -------------------------------------------------------------------------- */
.reasoning {
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 14px 0;
  padding: 12px 20px;
  border: 1px solid var(--bezel-outer-border);
  border-radius: 16px;
  background: rgba(12, 14, 20, 0.78);
  backdrop-filter: blur(20px);
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.08), 0 8px 24px rgba(0, 0, 0, 0.3);
  overflow-x: auto;
  white-space: nowrap;
}

.reasoning-title {
  color: var(--brand-orange);
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.reasoning-step {
  font-size: 12.5px;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: color var(--duration-fast) var(--ease-out), opacity var(--duration-fast) var(--ease-out);
}

.reasoning-step.completed {
  color: var(--color-emerald);
  font-weight: 500;
}

.reasoning-step.active {
  color: var(--brand-orange-bright);
  font-weight: 600;
  animation: reasoning-pulse 1.8s infinite var(--ease-in-out);
}

@keyframes reasoning-pulse {
  0%, 100% { opacity: 0.8; }
  50% { opacity: 1; text-shadow: 0 0 12px var(--brand-orange-glow); }
}

.reasoning-step.pending {
  color: var(--text-dim);
}

/* --------------------------------------------------------------------------
   CITATIONS & SOURCES (ISLAND CHIPS)
   -------------------------------------------------------------------------- */
.citations {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.citations-label {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-right: 4px;
}

.citation-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 5px 12px 5px 6px;
  border: 1px solid var(--brand-orange-border);
  border-radius: 999px;
  background: var(--brand-orange-subtle);
  font-size: 12px;
  color: #e2e8f0;
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.08);
  transition:
    transform var(--duration-fast) var(--ease-spring),
    border-color var(--duration-fast) var(--ease-out),
    box-shadow var(--duration-fast) var(--ease-out);
  cursor: default;
}

@media (hover: hover) and (pointer: fine) {
  .citation-chip:hover {
    transform: translateY(-1.5px);
    border-color: var(--brand-orange-bright);
    background: rgba(255, 103, 0, 0.14);
    box-shadow: 0 6px 18px rgba(255, 103, 0, 0.22);
  }
}

.citation-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 19px;
  height: 19px;
  border-radius: 50%;
  flex-shrink: 0;
  background: linear-gradient(135deg, var(--brand-orange), var(--brand-orange-bright));
  color: #fff;
  font-size: 10px;
  font-weight: 700;
}

.citation-name {
  color: #e2e8f0;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citation-page {
  color: var(--brand-orange-light);
  font-size: 11px;
  font-weight: 600;
  padding-left: 6px;
  border-left: 1px solid rgba(255, 103, 0, 0.35);
}

/* Metadata & Telemetry Row */
.metadata {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.metadata span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  color: var(--text-secondary);
  font-size: 11.5px;
}

.metadata span b {
  color: #ffffff;
}

.ragas-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid;
  font-size: 11.5px;
}

/* --------------------------------------------------------------------------
   CHAT INPUT DOCK: AMBIENT GLOW & TACTILE SUBMIT
   -------------------------------------------------------------------------- */
[data-testid="stBottom"], [data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"], [data-testid="stBottomBlockContainer"] > div {
  background: transparent !important;
  box-shadow: none !important;
}

[data-testid="stBottomBlockContainer"] {
  padding: 16px 24px 30px !important;
}

[data-testid="stChatInput"] {
  position: relative !important;
  max-width: 980px;
  margin: 0 auto !important;
  border: 1px solid var(--brand-orange-border) !important;
  border-radius: 20px !important;
  background: rgba(12, 14, 20, 0.9) !important;
  backdrop-filter: blur(28px) !important;
  box-shadow:
    inset 0 1px 1px rgba(255, 255, 255, 0.12),
    0 10px 36px rgba(0, 0, 0, 0.55),
    0 0 20px rgba(255, 103, 0, 0.1) !important;
  transition:
    border-color var(--duration-fast) var(--ease-out),
    box-shadow var(--duration-fast) var(--ease-out) !important;
}

[data-testid="stChatInput"]:focus-within {
  border-color: var(--brand-orange) !important;
  box-shadow:
    inset 0 1px 1px rgba(255, 255, 255, 0.2),
    0 12px 42px rgba(0, 0, 0, 0.65),
    0 0 32px rgba(255, 103, 0, 0.28) !important;
}

[data-testid="stChatInput"] > div,
[data-testid="stChatInput"] [data-baseweb="textarea"],
[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] [data-baseweb="input"] {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
}

[data-testid="stChatInput"] textarea {
  color: #f8fafc !important;
  font-size: 15px !important;
  line-height: 1.5 !important;
}

[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"] {
  background: linear-gradient(135deg, var(--brand-orange), var(--brand-orange-bright)) !important;
  border-radius: 50% !important;
  color: white !important;
  box-shadow: 0 4px 14px rgba(255, 103, 0, 0.4) !important;
  transition:
    transform var(--duration-fast) var(--ease-spring),
    box-shadow var(--duration-fast) var(--ease-out) !important;
}

@media (hover: hover) and (pointer: fine) {
  [data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"]:hover {
    transform: scale(1.08) !important;
    box-shadow: 0 6px 20px rgba(255, 103, 0, 0.55) !important;
  }
}

[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"]:active {
  transform: scale(0.92) !important;
}

/* --------------------------------------------------------------------------
   AUTH SCREEN & GOOGLE SSO (LUXURY DOUBLE-BEZEL CARD)
   -------------------------------------------------------------------------- */
#auth-welcome-container {
  animation: message-rise var(--duration-smooth) var(--ease-out) both;
}

.auth-welcome-spark {
  width: 58px;
  height: 58px;
  margin: 0 auto 16px;
  display: grid;
  place-items: center;
  border-radius: 18px;
  border: 1px solid var(--brand-orange-border);
  color: var(--brand-orange);
  font-size: 28px;
  box-shadow:
    inset 0 1px 1px rgba(255, 255, 255, 0.2),
    0 0 32px rgba(255, 103, 0, 0.35);
  background: rgba(14, 16, 24, 0.9);
  transition: transform var(--duration-fast) var(--ease-spring);
}

.auth-welcome-spark:hover {
  transform: scale(1.08) rotate(4deg);
}

.auth-google-btn {
  text-decoration: none !important;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  width: 100%;
  padding: 13px 20px;
  background: rgba(16, 19, 28, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 14px;
  color: #f8fafc !important;
  font-family: var(--font-sans) !important;
  font-size: 14.5px;
  font-weight: 600;
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.1), 0 6px 20px rgba(0, 0, 0, 0.4);
  transition:
    transform var(--duration-fast) var(--ease-spring),
    background var(--duration-fast) var(--ease-out),
    border-color var(--duration-fast) var(--ease-out),
    box-shadow var(--duration-fast) var(--ease-out);
  margin-bottom: 14px;
  cursor: pointer;
}

@media (hover: hover) and (pointer: fine) {
  .auth-google-btn:hover {
    transform: translateY(-2px);
    background: rgba(22, 26, 38, 0.98);
    border-color: rgba(255, 255, 255, 0.28);
    box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.2), 0 10px 28px rgba(0, 0, 0, 0.55);
  }
}

.auth-google-btn:active {
  transform: scale(0.975);
}

/* Tabs */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  background: transparent !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
  gap: 8px !important;
}

[data-testid="stTabs"] [data-baseweb="tab"] {
  font-family: var(--font-display) !important;
  font-weight: 500 !important;
  font-size: 15px !important;
  color: var(--text-muted) !important;
  padding: 10px 20px !important;
  border-radius: 12px 12px 0 0 !important;
  letter-spacing: 0.04em !important;
  text-transform: uppercase !important;
  transition: color var(--duration-fast) var(--ease-out) !important;
}

[data-testid="stTabs"] [data-baseweb="tab"]:hover {
  color: #ffffff !important;
}

[data-testid="stTabs"] [aria-selected="true"] {
  color: var(--brand-orange) !important;
}

[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
  background-color: var(--brand-orange) !important;
  height: 2.5px !important;
  box-shadow: 0 0 10px var(--brand-orange-glow) !important;
}

/* Form Buttons */
.stFormSubmitButton > button {
  font-family: var(--font-display) !important;
  font-weight: 500 !important;
  letter-spacing: 0.04em !important;
  text-transform: uppercase !important;
  border-radius: 14px !important;
  height: 48px !important;
  font-size: 16px !important;
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.35), 0 6px 20px rgba(255, 103, 0, 0.35) !important;
  transition: transform var(--duration-fast) var(--ease-spring), box-shadow var(--duration-fast) var(--ease-out) !important;
}

@media (hover: hover) and (pointer: fine) {
  .stFormSubmitButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.5), 0 10px 28px rgba(255, 103, 0, 0.5) !important;
  }
}

.stFormSubmitButton > button:active {
  transform: scale(0.975) !important;
}

/* --------------------------------------------------------------------------
   ACCESSIBILITY & REDUCED MOTION
   -------------------------------------------------------------------------- */
@media (prefers-reduced-motion: reduce) {
  *, ::before, ::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}

/* Responsive Overrides */
@media (max-width: 850px) {
  .hero h1 { font-size: 36px; }
  .assistant-avatar { width: 40px; min-width: 40px; height: 40px; }
  .profile { position: static; margin-top: 24px; }
  [data-testid="stMainBlockContainer"] { padding: 16px 18px 120px; }
}
</style>

#oauth-instant-overlay { display: none !important; }
body.oauth-authenticating #oauth-instant-overlay { display: none !important; }
"""

class ThemeEngine:
    """Deep ThemeEngine module encapsulating design tokens, typography, and styling."""

    @classmethod
    def get_theme_css(cls, bg_url: Optional[str] = None) -> str:
        """Return the compiled theme CSS with background URL injected."""
        if bg_url is None:
            try:
                from core.ui import background_data_url
                bg_url = background_data_url()
            except Exception:
                bg_url = ""
        return THEME_CSS_TEMPLATE.replace("{bg_url}", bg_url or "")

    @classmethod
    def inject_theme(cls, bg_url: Optional[str] = None) -> None:
        """Inject the compiled Obsidian Ember theme into the active Streamlit app."""
        try:
            import streamlit as st
            css = cls.get_theme_css(bg_url=bg_url)
            st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)
        except Exception as exc:
            logger.warning("Failed to inject theme into Streamlit: %s", exc)


def inject_theme(bg_url: Optional[str] = None) -> None:
    """Convenience function to inject theme."""
    ThemeEngine.inject_theme(bg_url)


def get_theme_css(bg_url: Optional[str] = None) -> str:
    """Convenience function to get compiled theme CSS."""
    return ThemeEngine.get_theme_css(bg_url)
