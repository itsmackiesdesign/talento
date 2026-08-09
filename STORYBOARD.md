# talento — Cinematic Landing Storyboard

The experience opens with a 7.6-second authored prelude, then uses measured `[data-shot]` DOM geometry. Each shot is sampled locally from `0..1`; scene and copy share the same named range. Resize and font completion trigger remeasurement.

## Intro prelude

The live Open Portal actor enters from depth, completes a weighted multi-axis X/Y/Z orbit, and passes the product thesis — candidate already in Telegram → open access → move talent into work. From 72% it settles into the exact `signal` pose while the overlay fades, so the intro and landing share one continuous WebGL object with no SVG swap or position jump.

| Shot / anchor | Narrative job | Actor pose / screen anchor | Copy zone and depth | Primary motion / envelope | Continuity | Mobile recompose | Reduced-motion pose |
|---|---|---|---|---|---|---|---|
| `signal` | Introduce the brand as access to talent | Portal components separated, then assembled at `(.50,.48)` | Center type behind actor; human frames in deep background | Actor; assemble `.00–.42`, logo hold `.42–.78`, release `.78–1` | Blue edge light becomes the persistent landmark | One portal, three vertical frames, shorter sequence | Complete mark with static blue rim |
| `open-access` | State the product promise | Portal front-facing at `(.73,.47)`, slight three-quarter tilt | Copy left; actor may cross oversized decorative type but never body copy | Camera; slow push, hold `.20–.72` | Same actor and light direction | Portal above, copy and CTA below | Static front-facing portal |
| `discover` | Show vacancy discovery entirely in Telegram | Portal shifts to `(.25,.50)`; Telegram dialogue occupies right | Copy left/top, dialogue foreground | Frame/type; language → branch → vacancy messages | Blue message edge follows portal opening | Dialogue fills viewport; one message group at a time | Final vacancy card visible |
| `apply` | Prove the form is a conversation with eight input types | Portal becomes an aperture behind the active question at `(.63,.48)` | Copy left; one question card foreground | Actor; question cards replace each other, long hold | Vacancy card compresses into first question | One full-screen question and large reply controls | Three representative question types stacked |
| `transfer` | Make Telegram → HR the unforgettable product-native hero moment | Application card crosses through portal from `z-` to `z+`, anchor `(.50,.50)` | Minimal copy at upper-left; no competing UI | Camera; cross threshold `.18–.72`, HR frame resolves `.72–1` | Same candidate/application card is traceable | Vertical Telegram → portal → HR path | Side-by-side before/after with connector |
| `manage` | Show the real operational workspace | Portal becomes a thin blue route behind Dashboard → Kanban → detail | Copy top-left; real UI owns center/right | Actor; one card moves New → Interview → Offer, then expands | Application card inherited from transfer | Sequential macro fragments: KPI, Kanban, candidate drawer | Static product montage |
| `system` | Explain multilingual and product depth | Portal separates into seven concentric system layers at `(.72,.50)` | Copy left; language switch and capabilities foreground | Frame/type then actor; RU→UZ→EN, layers separate after hold | Geometry stays fixed while language changes | Vertical capability chapters, one active module | Complete product map with all labels |
| `resolution` | Close the loop and convert | All layers reassemble into front-facing portal, then lowercase wordmark | Centered CTA in foreground; FAQ/footer below normal flow | Actor; reassemble `.00–.38`, hold `.38–1` | Returns to the opening silhouette | Static logo, large stacked CTAs | Identical static final pose |

## Transition contract

- Every boundary is a pure function of `{ shotId, localProgress }`; no one-way callbacks.
- Previous copy yields before a large actor/camera move begins.
- Each boundary will be captured at previous hold, 25%, midpoint, 75% and next hold; one reverse and one rapid two-shot jump are mandatory.
- The final shot owns the resolved pose explicitly and never reuses the previous segment start.
