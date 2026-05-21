/**
 * Role-aware shell that routes the 6 views by `useAppStore.currentView`.
 * Operator sees the 5 warehouse views; admin sees them + the System tab.
 * Data flows via TanStack Query; the WS event stream is mounted once here.
 */
import { lazy, Suspense, useEffect } from 'react'
import { Header } from '@/components/layout/Header'
import { Sidebar } from '@/components/layout/Sidebar'
import { StatusBar } from '@/components/layout/StatusBar'
import { useEventStream } from '@/hooks/useEventStream'
import { useTheme } from '@/hooks/useTheme'
import { useMe } from '@/lib/api'
import { useAppStore } from '@/lib/store'

// Lazy-load pages so the heavy R3F bundle is only fetched when the user
// lands on Overview (or refreshes there).
const OverviewPage  = lazy(() => import('@/pages/OverviewPage').then((m) => ({ default: m.OverviewPage })))
const EntriesPage   = lazy(() => import('@/pages/EntriesPage').then((m)  => ({ default: m.EntriesPage })))
const ZonesPage     = lazy(() => import('@/pages/ZonesPage').then((m)    => ({ default: m.ZonesPage })))
const AnomaliesPage = lazy(() => import('@/pages/AnomaliesPage').then((m)=> ({ default: m.AnomaliesPage })))
const CamerasPage   = lazy(() => import('@/pages/CamerasPage').then((m)  => ({ default: m.CamerasPage })))
const SystemPage    = lazy(() => import('@/pages/SystemPage').then((m)   => ({ default: m.SystemPage })))

function PageLoader() {
  return (
    <div className="h-[200px] grid place-items-center text-xs text-muted-foreground">
      Chargement…
    </div>
  )
}

function PageRouter() {
  const view = useAppStore((s) => s.currentView)
  const me   = useMe()
  const role = me.data?.role ?? 'operator'

  // Admin-only fallback: if the operator somehow lands on /system, redirect.
  const safeView = view === 'system' && role !== 'admin' ? 'overview' : view

  return (
    <Suspense fallback={<PageLoader />}>
      {safeView === 'overview'  && <OverviewPage />}
      {safeView === 'entries'   && <EntriesPage />}
      {safeView === 'zones'     && <ZonesPage />}
      {safeView === 'anomalies' && <AnomaliesPage />}
      {safeView === 'cameras'   && <CamerasPage />}
      {safeView === 'system'    && <SystemPage />}
    </Suspense>
  )
}

export function App() {
  useTheme()           // apply dark/light class on <html>
  useEventStream(true) // single WS connection for the whole app

  const view = useAppStore((s) => s.currentView)
  useEffect(() => {
    document.title = `LOGIVISION — ${view}`
  }, [view])

  return (
    <div className="min-h-screen flex flex-col">
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <main className="flex-1 min-w-0 flex flex-col">
          <Header />
          <div className="flex-1 overflow-auto px-6 py-5">
            <PageRouter />
          </div>
        </main>
      </div>
      <StatusBar />
    </div>
  )
}
