# AGENTS.md — Global Agent Design & Engineering Directives

This repository and environment are equipped with an elite suite of 33 frontend design, motion, and interaction engineering skills located in `.agents/skills/` (and globally in `~/.gemini/config/skills/`, `~/.claude/skills/`, `~/.codex/skills/`, and `~/.agents/skills/`).

## Mandatory UI/UX Skill Activation

Whenever the user asks to **design, build, recreate, style, or enhance an interactive UI**, any agent (Antigravity, Codex, Claude Code, GitHub Copilot, Cursor) **MUST** activate and adhere to the following skills:

1. **`design-motion-principles` & `animate`**:
   - Tri-designer motion framework (Emil Kowalski, Jakub Krehel, Jhey Tompkins).
   - Frequency Gate: High-frequency actions (<200ms or instant); medium actions (180-280ms cubic-bezier).
   - Zero generic linear easing. Use physics curves (e.g. `cubic-bezier(0.23, 1, 0.32, 1)` or `cubic-bezier(0.16, 1, 0.3, 1)`).
   - Tactile active press feedback on all buttons: `transform: scale(0.975)`.
   - Mandatory `prefers-reduced-motion` overrides.

2. **`design-taste-frontend` & `high-end-visual-design`**:
   - **Anti-Slop Directive**: Avoid generic AI purple gradients, centered card-in-card soup, and flat borders.
   - **Double-Bezel Architecture (Doppelrand)**: Machine-like nested shells (`outer shell` with hairline border + `inner core` with inset highlight and concentric squircle radius).
   - **Nested CTA / Island Buttons**: Trailing icons nested in distinct circular pill chips that translate on hover (`group-hover:translate-x-1`).
   - **Spatial Rhythm**: Generous whitespace, macro-spacing, and clear visual hierarchy.

3. **`awesome-claude-design` & `stitch-design-taste`**:
   - Strict `DESIGN.md` tokens for semantic colors, dark glassmorphism surfaces (`backdrop-filter: blur(24px)`), and typography contrast.

4. **`refactoring-ui` & `ui-ux-pro-max`**:
   - Typographic hierarchy: High-impact display font (`Bebas Neue` / `Plus Jakarta Sans`) + readable UI body (`Inter`) + tabular metrics (`Space Mono`).
