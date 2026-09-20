# GEMINI.md — Antigravity Assistant & Agent Directives

## Mandatory Skill Activation & UI/UX Standards

This repository is equipped with 33 specialized design, motion, and interaction engineering skills in `.agents/skills/`.
Whenever requested to **design, recreate, renovate, or touch any UI/UX or styling**, Antigravity MUST adhere to the following principles:

1. **Motion Principles (`design-motion-principles`, `animate`)**:
   - Apply physics-based spring curves (e.g. `cubic-bezier(0.23, 1, 0.32, 1)` or `cubic-bezier(0.32, 0.72, 0, 1)`).
   - Frequency Gate: High frequency interactions < 200ms or instant; standard interactions 180-280ms.
   - Tactile active press feedback on all buttons: `transform: scale(0.975)`.
   - Full `prefers-reduced-motion` compliance.

2. **Visual Hierarchy & Anti-Slop (`design-taste-frontend`, `high-end-visual-design`, `refactoring-ui`)**:
   - Double-Bezel Architecture (Doppelrand): Machine-like nested shells (`outer shell` hairline border `border: 1px solid rgba(255,255,255,0.08)`, `bg-white/[0.02]`, `inner core` with inset highlight `box-shadow: inset 0 1px 1px rgba(255,255,255,0.12)`).
   - Concentric Squircle Radii: Outer radius strictly greater than inner radius (e.g., `radius-outer = radius-inner + padding`).
   - Button-in-Button Pattern: Trailing icons and tags nested in distinct circular pill chips that shift subtly on hover (`translate-x-1`).
   - Deep Obsidian Surfaces: Dark glassmorphism (`#07080b`, `#0d0e14`, `backdrop-filter: blur(24px)`), with warm ember accents (`#ff7a00`).

3. **Typography Standards (`refactoring-ui`, `ui-ux-pro-max`)**:
   - Display & Hero: `Bebas Neue` / `Plus Jakarta Sans`.
   - Body & Interface: `Inter`.
   - Code & Metrics: `Space Mono`.
