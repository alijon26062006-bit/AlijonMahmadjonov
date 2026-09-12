# AVERIX brand system

Everything here is derived from the supplied logo. The mark's geometry and its two
colours are reproduced exactly — nothing is restyled, recoloured or "modernised".

## The mark

Three chamfered bars stack into an ascending `A`: a leaning stroke, then two
crossbars whose ends are cut at the same angle. It reads as both a letter and a
rising structure — apt for a platform that assembles software projects in stages.

| Asset | Use |
| --- | --- |
| `averix-mark.svg` | Primary. Traced 1:1 from the original; exact brand colours. |
| `averix-mark-mono.svg` | Inherits `currentColor`. Favicons, embossing, single-colour print. |
| `averix-logo-original.png` | The file as supplied by the owner. Reference, never edited. |
| `averix-mark.png` / `-transparent.png` | Tight crops of the original raster for contexts that cannot take SVG. |

The wordmark is set in type rather than drawn, so it stays crisp at every size:
the app composes `averix-mark.svg` with `AVERIX` in the brand sans at
`weight 700`, `tracking 0.14em`, uppercase. See `apps/web/components/brand/Logo.tsx`.

**Clear space** — at least 25% of the mark's height on every side.
**Minimum size** — 16px tall for the mark alone, 20px when paired with the wordmark.
**Never** rotate, shear, recolour, outline, add a shadow to, or place the mark on a
busy photograph. On imagery use a solid surface chip behind it.

## Colour

Both brand colours are sampled from the mark:

| Token | Hex | Role |
| --- | --- | --- |
| `--av-brand` | `#7017C8` | Identity and primary action. Used sparingly and always flat. |
| `--av-accent` / `--av-success` | `#018D46` | Verified, available, approved, released. |

The green is not decorative — it carries a single meaning across the product
(*this is confirmed*), which is why verification badges, availability and approved
milestones all use it and nothing else does.

Neutrals are a cool slate with a faint violet cast so they sit with the brand
rather than fighting it. Surfaces carry the product; violet appears in small,
deliberate doses — a primary button, a selected tab, a match score. There are no
brand gradients, no glows, and no tinted glass anywhere in the system.

`red` / `amber` / `blue` cover danger, warning and information. Info is blue
specifically so that "informational" never reads as "brand".

## Themes

Light, dark and system. Light is the default; dark applies on an explicit choice
(`data-theme="dark"`) or from `prefers-color-scheme` when no choice has been made.
Every colour is defined in the light block first, so a token can never be missing
in one theme.

## Type

`Inter` for the interface, `JetBrains Mono` for code, repository names, technology
tags and money. The scale starts at 13px base for mobile density, with negative
tracking on the display sizes. No headline larger than 31px anywhere in the product.

## Tokens

`tokens.json` is the single source of truth. `npm run tokens` regenerates
`apps/web/styles/tokens.css` and `apps/web/lib/breakpoints.ts` from it. Do not edit
the generated files.
