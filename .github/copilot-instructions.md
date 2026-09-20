# GitHub Copilot & VS Code Copilot Instructions — UI/UX & Motion Directives

When assisting with any user interface, CSS, HTML, styling, or frontend interaction code in this repository:

## Mandatory Skill Activation
Adhere to the installed skills located in `.agents/skills/` (and globally in `~/.agents/skills/`, `~/.gemini/config/skills/`, `~/.claude/skills/`, and `~/.codex/skills/`):
- `design-motion-principles`: Physics-based spring animations, Emil Kowalski duration constraints, active press feedback (`transform: scale(0.975)`), and `prefers-reduced-motion`.
- `design-taste-frontend` & `high-end-visual-design`: Anti-slop guidelines, double-bezel (Doppelrand) container architecture, nested button-in-button trailing icon pattern, subtle hairlines, and refined micro-textures.
- `awesome-claude-design` & `stitch-design-taste`: Rich tokenized design systems with dark glassmorphism surfaces (`backdrop-filter: blur(24px)`).
- `refactoring-ui` & `ui-ux-pro-max`: Typographic hierarchy (Bebas Neue display headings, Inter / Plus Jakarta Sans readable text, Space Mono technical metrics), spacing scales, and high visual contrast without cheap gradients.

## UI Implementation Guidelines
1. **Never generate generic AI slop**: No 1px flat grey borders, no plain purple gradients, no card-in-card nesting without concentric squircle radii.
2. **Double-Bezel Architecture**: Card components should feature an outer hairline boundary (`border: 1px solid rgba(255, 255, 255, 0.08)`) with an inner core containing subtle top-highlight inset shadows (`box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.12)`).
3. **Motion**: Use cubic-bezier physics curves such as `cubic-bezier(0.23, 1, 0.32, 1)` or `cubic-bezier(0.16, 1, 0.3, 1)` rather than default `linear` or `ease-in-out`.
4. **Streamlit Escaping**: If writing CSS within Python Streamlit f-strings (`st.markdown(f"""...""", unsafe_allow_html=True)`), ALWAYS double escape curly braces as `{{` and `}}`.
