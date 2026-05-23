# LOGIVISION Frontend — how it's built, how to run it, where each piece lives

Single-page React app served by the FastAPI gateway at
`http://localhost:8000/` (production build) or by the Vite dev server
at `http://localhost:5173/` (HMR during development).

```
Vite 5  +  React 18  +  TypeScript  +  Tailwind 3  +  TanStack Query 5
+ Zustand (UI state)  +  React Three Fiber (3D twin)  +  Recharts
+ Framer Motion       +  Lucide-react icons
```

---

## How to run

### Dev mode (recommended for UI work)

Vite dev server on `:5173` with Hot Module Reload. All `/api/*` and
`/ws/*` requests proxy to `:8000` where the FastAPI gateway runs.

```bash
# 1. Install once
cd frontend
npm install

# 2. Bring up the backend on :8000 (in a separate terminal)
cd ..
make api                       # or: LOGIVISION_ROLE=admin make api  for the Système tab

# 3. Start the dev server
cd frontend
npm run dev                    # http://localhost:5173
```

Edit any `.tsx` → browser reloads instantly.

### Production build (what the soutenance / Classroom uses)

```bash
cd frontend
npm run build                  # produces frontend/dist/
cd ..
make api                       # serves frontend/dist/ at http://localhost:8000/
```

### Type-checking only (CI does this automatically)

```bash
cd frontend
npx tsc --noEmit
```

---

## Directory layout

```
frontend/
├── src/
│   ├── App.tsx                     # top-level router; role-aware sidebar
│   ├── main.tsx                    # React mount + providers
│   ├── app/
│   │   └── globals.css             # CSS variables, Tailwind plugins
│   ├── components/
│   │   ├── layout/                 # sidebar, header, command palette, status bar
│   │   ├── dashboard/              # KpiStrip, top-of-Overview tiles
│   │   ├── digital-twin/           # R3F Canvas, Floor, Zone3D, HeatmapLayer
│   │   ├── cameras/                # AnalyticalCameraFeed (MJPEG + SVG overlays)
│   │   ├── predictions/            # CongestionPanel, AiModelStatus
│   │   ├── insights/               # InsightRail / InsightChain cards
│   │   └── ui/                     # shadcn-style primitives (Button, Card, etc.)
│   ├── hooks/
│   │   ├── useTheme.ts             # 'dark' class on <html>, persisted in localStorage
│   │   ├── useMe.ts                # /api/me - role gate
│   │   └── useEventStream.ts       # WebSocket /ws/events - live anomalies + heartbeats
│   ├── lib/
│   │   ├── api.ts                  # TanStack-Query hooks for every /api/* endpoint
│   │   ├── types.ts                # TypeScript interfaces shared across components
│   │   ├── store.ts                # Zustand slice for UI state (selectedZone, anomalies)
│   │   └── utils.ts                # cn(), formatNumber(), formatRelative()
│   ├── pages/
│   │   ├── OverviewPage.tsx        # Vue d'ensemble (operator hero)
│   │   ├── CamerasPage.tsx         # 5 analytical camera tiles
│   │   ├── ZonesPage.tsx           # per-zone occupancy cards
│   │   ├── AnomaliesPage.tsx       # severity-coloured event feed
│   │   ├── EntriesPage.tsx         # Entrées/Sorties journal + KPIs
│   │   └── SystemPage.tsx          # admin only: MLflow runs, drift, benchmarks
│   └── providers/                  # ThemeProvider, QueryProvider
├── public/                         # static assets (favicon, logos)
├── index.html                      # Vite entry, <link>s Inter + JetBrains Mono
├── vite.config.ts                  # path alias @ -> src; proxy /api + /ws -> :8000
├── tailwind.config.ts              # design tokens (electric, emerald, coral, etc.)
├── postcss.config.mjs
├── tsconfig.json
└── package.json
```

---

## Views (one per sidebar item)

### Caméras (default landing)

`CamerasPage.tsx`. Five tiles, one per `CAM0N` from
`infra/cameras.example.yaml`. Each tile streams MJPEG from
`/api/cameras/{id}/stream.mjpg` and renders an SVG overlay with the
real Kafka detections for that camera (read via the
`AnalyticalCameraFeed` component). Status badges:

| Badge | Meaning |
|---|---|
| `live · kafka` (green) | Both the MJPEG feed AND a recent detection arrived from Kafka. |
| `feed only` (electric blue) | MJPEG plays but no inference. Start `make inference-worker`. |
| `offline` (slate) | No raw-frames in the last 30 s. Start `make frame-grabber`. |

### Vue d'ensemble (operator hero)

`OverviewPage.tsx`. KPI strip at the top + 3D R3F twin + Congestion
panel + InsightRail + analytical camera grid at the bottom. The twin
clicks through to per-zone detail. Heatmap toggles on the twin's
ground plane drive different layers (traffic / shelf access /
idle / bottleneck).

The **AI Model Status** panel in the right rail surfaces the trained
LSTM (loaded from `ml/artifacts/congestion_lstm/model.pt`) and the
**Congestion prévue** header badge flips between `LSTM · PRSA · v1`
(emerald) when the trained model produced the forecast and `rule v0`
(amber) when the rule-based fallback fired.

### Zones

`ZonesPage.tsx`. Per-zone occupancy cards driven by
`infra/zones.example.yaml`. Click a zone → side panel with the
detection log filtered to that zone.

### Anomalies

`AnomaliesPage.tsx`. Severity-coloured cards (critical → coral,
warning → amber, info → electric). Real CEP events from the
`events` topic — no demo data fallback. Empty list = "no anomalies"
banner.

### Entrées/Sorties

`EntriesPage.tsx`. KPI tiles for today's entry/exit count + a
chronological journal. Driven by CEP events with
`event_type ∈ {entry, exit}`.

### Système (admin only)

`SystemPage.tsx`. Hidden by default. Set `LOGIVISION_ROLE=admin`
before `make api` to see it. Surfaces:
- MLflow runs (`/api/registry/runs`)
- Model Registry stages (`/api/registry/models`)
- Kafka topics + consumer lag (`/api/topics`)
- Drift reports (`/api/drift/reports`)
- Benchmarks (`/api/benchmarks`)

---

## Data flow (real, no fake fallbacks)

```
React component
   ↓ (TanStack Query hook in src/lib/api.ts)
GET /api/...     (FastAPI route in services/api/routers/client.py)
   ↓
Kafka topic peek + YAML config read
   ↓
events / detections / raw-frames topics
   ↓
inference_worker (YOLO + ByteTrack) + stream_processor (CEP rules)
   ↓
frame_grabber (MP4/RTSP → raw-frames + MinIO)
```

Live updates use `useEventStream()` → WebSocket `/ws/events` → Zustand
slice → components re-render on every new event.

---

## State (the two systems)

| Type | Tool | What it holds |
|---|---|---|
| Server state (cached, refetched) | **TanStack Query** | `/api/*` responses: zones, cameras, KPIs, predictions, model-info, anomalies, entries-exits, registry, drift. Refetch intervals tuned per endpoint (10 s for KPIs, 60 s for model-info, etc.). |
| Client state (ephemeral UI) | **Zustand** | `selectedZone`, `liveAnomalies` (from WS), `cmdkOpen`, theme toggle, "Reduce motion" preference. |

---

## Where to add a feature

| Goal | Edit |
|---|---|
| **New API hook** for a backend endpoint | `src/lib/api.ts` (add useFoo + type in `lib/types.ts`) |
| **New panel** on Overview | `src/components/predictions/` or `src/components/dashboard/`; mount in `pages/OverviewPage.tsx` |
| **New sidebar item / page** | `src/pages/FooPage.tsx`, register route in `App.tsx`, add to sidebar nav array |
| **New camera-tile overlay** | `src/components/cameras/AnalyticalCameraFeed.tsx` (SVG overlay block) |
| **New zone in the 3D twin** | edit `infra/zones.example.yaml` — the polygon is read at runtime, no code change |
| **New design token** (colour, font) | `tailwind.config.ts` + `src/app/globals.css` (CSS variables) |
| **New WS event handler** | `src/hooks/useEventStream.ts` |

---

## Design tokens (Tailwind classes)

Defined in `tailwind.config.ts`:

| Token | Use | Class |
|---|---|---|
| `electric` (#06B6D4) | Primary blue — info, links, "live" state | `bg-electric`, `text-electric` |
| `emerald` (#10B981) | Success, trained models, healthy | `bg-emerald`, `text-emerald` |
| `amber` (#F59E0B) | Warning, rule-based fallback | `bg-amber`, `text-amber` |
| `coral` (#EF4444) | Critical, alerts | `bg-coral`, `text-coral` |
| `glass-card` | The translucent rounded card style | utility class in `globals.css` |
| `shadow-soft` | Soft drop shadow | utility class |

Spacing, radii, and typography follow Tailwind defaults except font:
**Inter** (UI) + **JetBrains Mono** (tabular numbers, code).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Dashboard shows "—" everywhere with "waiting for pipeline" notice | Expected when Kafka has no events. Run `make frame-grabber SOURCE=datasets/raw/videos/Camera3.mp4 CAMERA=CAM03 FPS=2`, then `make inference-worker` and `make cep`. KPIs fill in within ~10 s. |
| Camera tile shows broken-image icon | The `Camera{N}.mp4` symlink is missing. Run `make camera-videos`. |
| "Système" tab not in sidebar | The API was started without admin role. Restart with `LOGIVISION_ROLE=admin make api`. |
| 3D twin renders a blank canvas | Browser blocked WebGL. Check `chrome://gpu` / Safari Develop menu → enable WebGL. A CSS-isometric fallback is on the roadmap. |
| `make frontend-build` fails with TS errors | Run `npx tsc --noEmit` to see the full error. Usually a missing field in `src/lib/types.ts` after a backend change. |
| Vite dev server can't reach the API (CORS / proxy error) | Make sure FastAPI is running on `:8000`. Vite proxy in `vite.config.ts` expects `:8000`; change if you ran the API on another port. |
| LSTM badge stays on `rule v0` even when the model is loaded | API didn't restart after the model was saved. Run `make worker-restart` and reload the dashboard. |

---

## Build sizes (last measured)

```
dist/assets/index-XXX.js                   ~222 KB │ gzip:  ~71 KB
dist/assets/OverviewPage-XXX.js          ~1,000 KB │ gzip: ~280 KB  (R3F heavy)
dist/assets/AnalyticalCameraFeed-XXX.js    ~5 KB   │ gzip:  ~2 KB
```

The R3F bundle dominates. It's lazy-loaded (only on the Overview
page), so Caméras / Zones / Anomalies / Entrées load fast. To further
reduce, the `leva` dev-only debug panel is stripped in production
via the Vite config.
