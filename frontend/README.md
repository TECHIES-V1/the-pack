# frontend — the Territory

React 18 + TypeScript + Vite · Tailwind (design tokens) · Zustand · native WebSocket with
an SSE fallback. The canvas is **React Flow** (`@xyflow/react`) + dagre + Framer Motion
(D2). This is the product's face and our declared moat (Doc 03).

## The one rule (Doc 03 §2)

**The UI renders only from the event stream.** No client-side orchestration, no business
logic, no direct Qwen calls, no client-side cost math. The client is a deterministic
function: the event log in, the UI state out. That lives in `src/events/reducer.ts` and is
unit-tested against the committed fixture pack.

## Layout

```
src/
  events/types.ts      the PackEvent envelope (mirrors schema/events.schema.json)
  events/reducer.ts    THE pure reducer — event log in, HuntView out
  events/reducer.test.ts  "given stream X, the final state is Y" over ../../fixtures
  store/huntStore.ts   Zustand wrapper around the reducer
  canvas/WolfNode.tsx  WolfCard (presentational) + WolfNode (React Flow node)
  canvas/Territory.tsx the live canvas, built from the store
  canvas/packLayout.ts dagre auto-layout (React Flow doesn't place nodes)
  pages/StatesGallery.tsx  every WolfNode state, for design review
  styles/tokens.css    design tokens (color/type/spacing/motion)
```

## Quickstart

```bash
pnpm install
pnpm test     # reducer snapshot tests over the fixture pack
pnpm build    # tsc -b && vite build
pnpm dev      # http://localhost:5173 — nav: Door / Territory / Gallery
```

## Reference, not dependency

The canvas wiring (state-driven node styling, `animated` edge toggling, the React Flow
setup) was lifted as a *pattern* from Firecrawl's Open Agent Builder (MIT). We did not
vendor it — see `docs/BORROWING.md`. Doc 03 mandates Vite; OAB was Next.js.

## Non-goals (Doc 03 §9)

No login UI. No settings page. No mobile Territory in P0. No client-side cost math (render
`tokens_spent` events only). No localStorage truths beyond a session id.
