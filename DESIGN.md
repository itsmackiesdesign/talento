# talento — Design System

## Art direction

**Open Portal:** a precise, cinematic bridge between a candidate's Telegram conversation and the HR workspace — black space, electric-blue energy, cold white type, photographed light and restrained motion.

Primary register: **Immersive 3D**. Secondary register: **Data / Product Premium**.

## Color tokens

| Name | Value | Token | Role |
|---|---:|---|---|
| System Black | `#050507` | `--tl-black` | Primary environment and negative space |
| Portal Blue | `#2F2BFF` | `--tl-blue` | Single brand accent, active controls and emissive portal edge |
| Clear White | `#FFFFFF` | `--tl-white` | Primary copy and logo on dark surfaces |
| Soft White | `#E9E9F2` | `--tl-soft` | Secondary copy and UI chrome |
| Graphite | `#111116` | `--tl-graphite` | Product surfaces and raised panels |
| Steel | `#767686` | `--tl-steel` | Metadata and quiet borders |
| Blue Veil | `rgba(47,43,255,.18)` | `--tl-blue-veil` | Atmospheric light only |

No secondary saturated accent. Status colors appear only inside product UI where they carry meaning.

## Typography

- Display and wordmark support: **Rubik**, 400 / 700.
- Body and interface: **Noto Sans**, 400 / 700.
- Hero: `clamp(4rem, 10vw, 10rem)`, line-height `0.88`, tracking `-0.065em`.
- Section title: `clamp(2.7rem, 6vw, 6.5rem)`, line-height `0.94`, tracking `-0.05em`.
- Body large: `clamp(1.05rem, 1.55vw, 1.35rem)`, line-height `1.55`.
- Label: `0.68rem–0.76rem`, uppercase, tracking `0.18em–0.26em`.
- Text measure: body max `44rem`; hero max `14ch`.

## Spacing and grid

- Desktop content gutter: `clamp(24px, 5vw, 80px)`.
- Mobile gutter: `20px`.
- Maximum editorial width: `1600px`.
- Primary grid: 12 columns desktop, 4 columns mobile.
- Semantic shot height: `110–150svh`; hero and transfer receive the longest dwell.
- Major radius: `28px`; controls: pill or `14px`; avoid a wall of rounded cards.

## Motion tokens

- Heavy ease: `cubic-bezier(.16, 1, .3, 1)`.
- Cinematic travel: `cubic-bezier(.76, 0, .24, 1)`.
- Micro interaction: `180–280ms`.
- Copy reveal: `700–950ms`, max `28px` travel.
- Shot envelope: enter `0–.22`, hold `.22–.70`, exit `.70–1`.
- Intro prelude: `7.6s` after the live scene reports ready; orbit `0–.72`, settle `.72–1`, overlay release from `.84`.
- Maximum two meaningful moving layers at once.
- No perpetual turntable rotation; the portal stops at authored poses.

## Surface and material rules

- Portal: bevelled polished metal, dark smoked-glass inner wall, electric-blue emissive cut edge.
- Product UI: clear opaque graphite panels with subtle borders; glass is limited to transition overlays.
- Lighting: neutral IBL/studio reflections plus one motivated cold key from upper frame-right.
- Grade: ACES renderer, thresholded bloom, restrained vignette and fine film grain.
- Depth: background human frames, midground portal, foreground DOM copy/product UI. Copy always wins.

## Accessibility and fallback

- WCAG AA contrast, visible focus ring in Portal Blue/white, semantic headings and keyboard controls.
- WebGL is decorative (`aria-hidden`); all meaning remains in DOM.
- Reduced motion receives composed static portal poses and normal document scrolling.
- Mobile uses a separately composed portal and product fragments, not a scaled desktop scene.
