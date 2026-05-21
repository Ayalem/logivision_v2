import { create } from 'zustand'
import type { LiveEvent } from './types'

export type ViewType =
  | 'overview'
  | 'entries'
  | 'zones'
  | 'anomalies'
  | 'cameras'
  | 'system'   // admin-only: MLflow runs / drift / benchmarks

export type HeatmapLayer = 'off' | 'traffic' | 'shelf' | 'idle' | 'bottleneck' | 'worker'

interface AppState {
  // Navigation / chrome
  currentView: ViewType
  sidebarCollapsed: boolean
  focusMode: boolean
  commandPaletteOpen: boolean

  // Filters
  selectedZone: string | null
  selectedCameraId: string | null
  searchQuery: string
  timeRange: '24h' | '7d' | '30d' | '90d' | '12m'

  // 3D twin — wow-factor toggles (Pillars 2, 3, 5)
  heatmap: HeatmapLayer
  showTrajectories: boolean
  showCollisions: boolean
  reduceMotion: boolean

  // Live event slice — fed by useEventStream, consumed by activity feed,
  // collision beacons, and the insight chain.
  live: {
    events: LiveEvent[]            // newest first; capped at 200
    lastEventTs: number | null
    wsState: 'idle' | 'live' | 'reconnecting' | 'error'
  }

  // Setters
  setView: (v: ViewType) => void
  toggleSidebar: () => void
  toggleFocusMode: () => void
  setCommandPaletteOpen: (open: boolean) => void
  setSelectedZone: (id: string | null) => void
  setSelectedCameraId: (id: string | null) => void
  setSearchQuery: (q: string) => void
  setTimeRange: (r: AppState['timeRange']) => void

  setHeatmap: (layer: HeatmapLayer) => void
  toggleTrajectories: () => void
  toggleCollisions: () => void
  toggleReduceMotion: () => void

  pushLiveEvent: (evt: LiveEvent) => void
  setWsState: (s: AppState['live']['wsState']) => void
}

const LIVE_BUFFER_MAX = 200

export const useAppStore = create<AppState>((set) => ({
  // Land on the Caméras view by default — the operator's primary
  // concern is what each camera sees. The Overview/3D twin lives one
  // click away in the sidebar.
  currentView: 'cameras',
  sidebarCollapsed: false,
  focusMode: false,
  commandPaletteOpen: false,

  selectedZone: null,
  selectedCameraId: null,
  searchQuery: '',
  timeRange: '7d',

  heatmap: 'traffic',
  showTrajectories: true,
  showCollisions: true,
  reduceMotion: false,

  live: { events: [], lastEventTs: null, wsState: 'idle' },

  setView:                (v) => set({ currentView: v }),
  toggleSidebar:          () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  toggleFocusMode:        () => set((s) => ({ focusMode: !s.focusMode })),
  setCommandPaletteOpen:  (open) => set({ commandPaletteOpen: open }),
  setSelectedZone:        (id) => set({ selectedZone: id }),
  setSelectedCameraId:    (id) => set({ selectedCameraId: id }),
  setSearchQuery:         (q) => set({ searchQuery: q }),
  setTimeRange:           (r) => set({ timeRange: r }),

  setHeatmap:           (layer) => set({ heatmap: layer }),
  toggleTrajectories:   () => set((s) => ({ showTrajectories: !s.showTrajectories })),
  toggleCollisions:     () => set((s) => ({ showCollisions: !s.showCollisions })),
  toggleReduceMotion:   () => set((s) => ({ reduceMotion: !s.reduceMotion })),

  pushLiveEvent: (evt) =>
    set((s) => {
      const events = [evt, ...s.live.events].slice(0, LIVE_BUFFER_MAX)
      return { live: { ...s.live, events, lastEventTs: evt.timestamp_ms } }
    }),
  setWsState: (wsState) => set((s) => ({ live: { ...s.live, wsState } })),
}))
