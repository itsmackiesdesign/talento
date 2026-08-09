# talento — Asset Ledger and Budget

| Asset | Source / provenance | Production output | Budget | Use |
|---|---|---|---:|---|
| Open Portal symbol and wordmark | Provided brand package, authored for talento | Optimized inline SVG + extruded code-native geometry | < 80 KB | Persistent hero actor, logo and icons |
| Rubik / Noto Sans | Provided open-source font files in brand package | Local WOFF2 | < 250 KB total | Display and body typography |
| Product UI | Existing React components and demo schema | Re-authored marketing-stage UI using real fields and seeded content | < 120 KB JS/CSS | Telegram, dashboard, Kanban and candidate detail shots |
| Human documentary frames | Generated with OpenAI ImageGen for this landing; no fake testimonials | `talento-human-frames.webp` (five-frame editorial contact sheet) | 66 KB | Intro and hero background |
| Environment light | Code-native drei Lightformers; no external HDRI | Runtime studio reflections | Included in lazy WebGL chunk | Portal reflections |
| Portal geometry | Generated from the provided Open Portal vector proportions | Shared beveled R3F geometry and physical materials | < 80k triangles, < 20 calls | All live 3D shots |
| Low-power fallback | Provided Open Portal brand symbol | Optimized SVG poster on a code-native blue light field | < 20 KB | Reduced-motion / unsupported WebGL |
| Favicon and app icons | Provided brand package | PNG/SVG copied to public | < 200 KB | Metadata and browser surfaces |

Initial shell remains below 200 KB gzip where practical; the Three/R3F stack is lazy-loaded after the DOM shell. No GIFs, placeholder stock dashboards, fake customer logos, reviews or metrics.
