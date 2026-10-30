# Design system

FIREWATCH X uses the **Orbital Intelligence** visual language: a near-black field, deep-navy glass
surfaces, hairline white borders with a gradient edge shell, editorial serif display type and one
restrained green accent. The intent is institutional satellite intelligence — calm, technical,
meditative — rather than a generic "AI dashboard".

Source of the language: `Arion-One-Orbital-Intelligence-DESIGN.md`.

## Colour

| Token | Value | Use |
| --- | --- | --- |
| Background | `#131315` | Page canvas |
| Surface | `#0B101D` | Glass panels, sidebar, header, popovers |
| Text primary (ink) | `#FFFFFF` | Headings, values |
| Text secondary (muted) | `#8C9099` | Body copy, labels |
| Faint | `#676C79` | Metadata, hints |
| Border | `#FFFFFF` at 6–14% | Hairlines, shells, controls |
| Accent | `#60D58B` | Interactive emphasis, healthy state, active nav |
| Secondary | `#72A5F9` | Informational state |
| Tertiary | `#62D5DD` | Rare contrast moments |

Fire-activity colours (`#FACC15`, `#FB923C`, `#EF4444`) are **semantic data colours** reserved for
severity scales and the disclaimer — never used for chrome, so amber always means "fire", not
"button".

## Typography

| Role | Font | Size / weight |
| --- | --- | --- |
| Display | Newsreader (400) | 34–40px, tracking −0.025em |
| Body | Inter (300) | 13–14px / 1.65 |
| Labels | Inter (500) | 10–11px uppercase, tracking 0.14–0.16em |
| Measurements / IDs | JetBrains Mono | 11–13px, tabular |

Display serif carries page titles and stat values; Inter carries interface copy; mono is reserved
for coordinates, timestamps, source codes and endpoint paths so measurements stay unambiguous.

## Surfaces and depth

- Every card is glass: `#0B101D` at 62–92% with 14px backdrop blur.
- Cards use a **gradient border shell**: a 1px wrapper carrying
  `linear-gradient(to bottom right, rgba(255,255,255,0.14), rgba(255,255,255,0.03), transparent)` with
  the content surface inset at a 1px smaller radius (12px → 11px).
- Shadows are glow-first, never heavy: `0 0 24px rgb(255 255 255 / 0.06)` inside panels,
  `0 0 18px rgb(96 213 139 / 0.18)` for halos, and a single lift shadow for popovers.
- Radii stay in the family 7 / 8 / 11 / 12 / 9999px (tags, controls, cards, shells, pills).

## Layout rhythm

Base unit 6px. Steps used: 6, 8, 10, 12, 14, 18, 22, 28. Section padding 28px (56px at large
breakpoints), card padding 18–22px, control height 32px, header 56px, sidebar 264px (72px rail).

## Background field

A perspective grid rendered behind the console: green hairlines on black, converging on a horizon
with a slow breathing pulse and a subtle pointer drift, faded into the chrome at the page edges.

Implemented as Canvas 2D (`OrbitalField.tsx`) rather than WebGL: the visual language is identical,
the bundle stays small in a data-critical app, the device pixel ratio is clamped to 2, and it falls
back to a static frame under `prefers-reduced-motion`. The CSS radial gradient underneath is the DOM
fallback if a 2D context is unavailable.

## Motion

Minimal: 150ms transitions on colour and border, 240ms `cubic-bezier(0.2, 1, 0.4, 1)` for panel
entry, 1000ms for the delivery meter, 4s breathing pulse for live indicators. All motion is disabled
under `prefers-reduced-motion`.

## Components

| Component | Recipe |
| --- | --- |
| Primary action | Off-white `#FAFAFA` pill, `#05070F` label, 8px vertical padding |
| Secondary action | Glass pill: hairline border, 4% white fill, muted label |
| Panel | Gradient shell → 11px inset surface → header 22px, body 22px |
| Stat tile | Label, serif figure at 30px, 12px hint, hairline border |
| Badge | Pill, hairline border in the semantic tone, 10px uppercase label |
| Nav item | 8px radius, quiet by default, 6% white fill + green icon when active |
| Popover | Glass card, 12px radius, lift shadow, 14px blur |

## Constraints

- One accent green; blue and cyan are informational only; amber/orange/red mean fire.
- No fills behind text except 4–6% white haze.
- No shadows on flat content; glow only on floating surfaces.
- Borders are hairlines at 6–14% white — never a solid light stroke.
- Never introduce a new radius, font size or spacing value outside the families above.
