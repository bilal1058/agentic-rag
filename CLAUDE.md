# CLAUDE.md — Claude Code Design Directives

## UI/UX & Motion Engineering Rules

When building or styling any frontend UI in this repository, always invoke the design principles from:
- `.agents/skills/design-motion-principles/SKILL.md`
- `.agents/skills/design-taste-frontend/SKILL.md`
- `.agents/skills/awesome-claude-design/SKILL.md`
- `.agents/skills/high-end-visual-design/SKILL.md`
- `.agents/skills/refactoring-ui/SKILL.md`

### Core Rules:
1. **Motion**: Use Emil Kowalski speed restraint (<250ms) for productivity tools, Jakub Krehel spring polish for consumer apps, and Jhey Tompkins CSS micro-interactions for creative touches. Always include `prefers-reduced-motion` compliance.
2. **Architecture**: Implement the Double-Bezel nested container pattern for cards, inputs, and dialogs.
3. **Typography**: Display/Headings in `Bebas Neue` / `Plus Jakarta Sans`, body copy in `Inter`, monospace metrics in `Space Mono`.
4. **Colors & Surfaces**: Deep obsidian palette (`#07080b` / `#0d0e14`) with ambient ember accents (`#ff7a00`), subtle hairlines (`rgba(255,255,255,0.08)`), and glassmorphism.
