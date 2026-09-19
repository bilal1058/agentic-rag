---
name: awesome-claude-design
description: Design system generator and catalog of 68 production-grade DESIGN.md brand aesthetics for Claude, Cursor, and Antigravity. Use when creating design systems, choosing brand aesthetics (Linear, Vercel, Stripe, Raycast, Supabase, etc.), scaffolding tokens, typography, colors, and building cohesive frontend interfaces.
---

# Awesome Claude Design & DESIGN.md Framework

A comprehensive framework and catalog of 68 ready-to-use design systems and `DESIGN.md` principles for AI coding agents. Hand an agent a `DESIGN.md` specification and it scaffolds a coherent, production-ready design system (tokens, colors, typography, components, preview cards, and UI kits) in a single shot without generic "AI-slop" styling.

---

## 1. What is DESIGN.md?

`DESIGN.md` is a single plain-text markdown specification describing a brand's visual language in a format AI agents can strictly adhere to.

| File | Primary Consumer | Purpose |
|---|---|---|
| `AGENTS.md` | Coding Agents | Architectural & implementation constraints |
| `DESIGN.md` | Design & Frontend Agents | Visual language, design tokens, typography, palette & component rules |

### The Core Principle
Keep **token, rule, and rationale in the same specification**. A Figma export tells an agent *what* to use but skips *why*. A loose marketing brief talks to humans ("approachable yet premium") but is too vague for an agent. `DESIGN.md` bridges the gap: specific enough for immediate code generation, while carrying the design rationale so the agent makes consistent aesthetic decisions on novel edge cases.

---

## 2. Core Structure of a DESIGN.md File

When generating or auditing an interface, follow this standardized template:

```markdown
# [Brand / Product Name] Design System

## 1. Brand Essence & Visual Tone
- **Archetype**: (e.g. Developer-first, Terminal-native, Luxury Editorial, Precision Fintech)
- **Primary Metaphor**: (e.g. Dark void with high-energy ember accents, broadsheet paper with ink typography)
- **Density**: (Compact / Standard / Spacious)

## 2. Color Palette & Semantic Tokens
- **Backgrounds**: Deep base, elevated card, popover/modal surface
- **Borders**: Hairline subtle (rgba 0.08), hover state (rgba 0.25), active state
- **Accents**: Primary brand accent, hover shift, glowing ambient aura
- **Typography Colors**: Heading primary (98%), body secondary (70%), muted/meta (45%)

## 3. Typography Hierarchy
- **Display / Headings**: Font family, weight, tracking/letter-spacing, line-height
- **Body Text**: Font family, readability size (14-16px), line-height (1.5-1.6)
- **Monospace / Metrics**: Font family for tabular data, code, latency, and citations

## 4. Component Rules & Micro-Interactions
- **Buttons**: Heights, padding, border-radius, active scale press (0.97-0.98), hover lifts
- **Input Fields**: Inset dark fill, ambient focus ring glow, label positioning
- **Cards & Surfaces**: Glassmorphism backdrop-blur, subtle elevation shadows, border contrast
- **Feedback & States**: Non-generic loading spinners, pill badges, interactive chips
```

---

## 3. Catalog of Curated Aesthetic Archetypes

Use these 68 battle-tested design system identities for instant scaffolding:

### AI & LLM Platforms
- **Claude (Anthropic)**: Warm terracotta accent (`#cc785c` / `#d97706`), warm ivory/parchment surfaces, clean editorial serif/sans hierarchy.
- **Agentic RAG / Modern AI**: Deep obsidian backdrop (`#090a0e`), electric ember/orange accents (`#ff7a00`), glassmorphic cards (`blur(24px)`), tactile press feedback.
- **VoltAgent**: Void-black canvas, emerald terminal accent (`#10b981`), monospace-first execution.
- **ElevenLabs**: Cinematic dark UI, audio-waveform visualizers, neon violet/cyan accents.
- **Ollama**: Terminal-first, monochrome stark simplicity, ASCII and monospace dominance.
- **Mistral AI**: French-engineered minimalism, deep charcoal with subtle lavender/purple highlights.

### Developer Tools & Productivity
- **Linear**: Ultra-minimalist dark theme, hair-thin borders (`1px solid rgba(255,255,255,0.08)`), keyboard-first shortcuts, subtle purple glow.
- **Vercel**: Stark black and white precision, Geist typography, geometric alignment, ultra-fast crisp transitions.
- **Raycast**: Deep charcoal chrome, vibrant hyper-saturated gradients, floating pill badges.
- **Cursor**: AI-first code editor aesthetic, subtle syntax highlighting, tabbed contextual drawers.
- **Superhuman**: Keyboard-first speed, luxury dark indigo palette, purple ambient glow, zero friction.
- **Supabase**: Dark emerald theme (`#3ecf8e`), monospace sql snippets, developer documentation aesthetic.

### Fintech & Precision
- **Stripe**: Elegantly restrained purple/indigo gradients, light mode clarity, weight-300 display typography.
- **Revolut**: Dark futuristic fintech, frosted glass cards, neon gradient accents.
- **Binance**: High-contrast Binance Yellow on obsidian black, trading-floor data density, numeric tabular mono fonts.

---

## 4. Design Scaffolding Checklist for Agents

When requested to scaffold or renovate a UI using Claude Design principles:
1. **Never use generic browser defaults**: Always define custom CSS variables for colors, surfaces, and typography.
2. **Constrain the palette**: 1 primary surface color, 1 elevated surface color, 1 text primary, 1 text muted, and 1-2 intentional accent colors.
3. **Typography pairs**: Always establish 1 high-character display font for headers + 1 clean neutral font for body + 1 monospace font for technical metrics.
4. **Tactile feedback**: Every interactive element must provide immediate visual feedback (hover lift `translateY(-1px)` or press scale `scale(0.98)`).
5. **Anti-Slop Rule**: Avoid generic purple-to-blue AI gradients, random floating bubbles, and non-functional pulsing borders.
