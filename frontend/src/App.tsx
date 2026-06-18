/**
 * Role-aware shell that routes the 6 views by `useAppStore.currentView`.
 * Operator sees the 5 warehouse views; admin sees them + the System tab.
 * Data flows via TanStack Query; the WS event stream is mounted once here.
 */
import { lazy, Suspense, useEffect } from 'react'
import { Header } from '@/components/layout/Header'
import { Sidebar } from '@/components/layout/Sidebar'
import { StatusBar } from '@/components/layout/StatusBar'
import { LoginPage } from '@/pages/LoginPage'
import { useEventStream } from '@/hooks/useEventStream'
import { useTheme } from '@/hooks/useTheme'
import { useAppStore } from '@/lib/store'
import { useTranslation } from '@/lib/i18n'

// Lazy-load pages
const OverviewPage   = lazy(() => import('@/pages/OverviewPage').then((m) => ({ default: m.OverviewPage })))
const EntriesPage    = lazy(() => import('@/pages/EntriesPage').then((m)  => ({ default: m.EntriesPage })))
const ZonesPage      = lazy(() => import('@/pages/ZonesPage').then((m)    => ({ default: m.ZonesPage })))
const AnomaliesPage  = lazy(() => import('@/pages/AnomaliesPage').then((m)=> ({ default: m.AnomaliesPage })))
const CamerasPage    = lazy(() => import('@/pages/CamerasPage').then((m)  => ({ default: m.CamerasPage })))
const SystemPage     = lazy(() => import('@/pages/SystemPage').then((m)   => ({ default: m.SystemPage })))
const AnalyticsPage  = lazy(() => import('@/pages/AnalyticsPage').then((m)=> ({ default: m.AnalyticsPage })))
const InventoryPage  = lazy(() => import('@/pages/InventoryPage').then((m)=> ({ default: m.InventoryPage })))
const WorkforcePage  = lazy(() => import('@/pages/WorkforcePage').then((m)=> ({ default: m.WorkforcePage })))
const SettingsPage   = lazy(() => import('@/pages/SettingsPage').then((m)  => ({ default: m.SettingsPage })))
const ProfilePage    = lazy(() => import('@/pages/ProfilePage').then((m)   => ({ default: m.ProfilePage })))
const MlMonitoringPage = lazy(() => import('@/pages/MlMonitoringPage').then((m) => ({ default: m.MlMonitoringPage })))
const UnauthorizedPage = lazy(() => import('@/pages/UnauthorizedPage').then((m) => ({ default: m.UnauthorizedPage })))
const ActivityLogPage = lazy(() => import('@/pages/ActivityLogPage').then((m) => ({ default: m.ActivityLogPage })))
const TasksPage = lazy(() => import('@/pages/TasksPage').then((m) => ({ default: m.TasksPage })))

function PageLoader() {
  return (
    <div className="h-[200px] grid place-items-center text-xs text-muted-foreground">
      Chargement…
    </div>
  )
}

function PageRouter() {
  const view = useAppStore((s) => s.currentView)
  const userRole = useAppStore((s) => s.userRole)
  const role = userRole ?? 'worker'

  // Admin-only check
  const adminOnlyViews: (typeof view)[] = ['system', 'ml-monitoring', 'analytics', 'zones', 'activity-log']
  const isUnauthorized = adminOnlyViews.includes(view) && role !== 'admin'

  return (
    <Suspense fallback={<PageLoader />}>
      {isUnauthorized ? (
        <UnauthorizedPage />
      ) : (
        <>
          {view === 'overview'   && <OverviewPage />}
          {view === 'entries'    && <EntriesPage />}
          {view === 'zones'      && <ZonesPage />}
          {view === 'anomalies'  && <AnomaliesPage />}
          {view === 'cameras'    && <CamerasPage />}
          {view === 'system'     && <SystemPage />}
          {view === 'ml-monitoring' && <MlMonitoringPage />}
          {view === 'analytics'  && <AnalyticsPage />}
          {view === 'inventory'  && <InventoryPage />}
          {view === 'workforce'  && <WorkforcePage />}
          {view === 'settings'   && <SettingsPage />}
          {view === 'profile'    && <ProfilePage />}
          {view === 'activity-log' && <ActivityLogPage />}
          {view === 'tasks'      && <TasksPage />}
        </>
      )}
    </Suspense>
  )
}

export function App() {
  useTheme()           // apply dark/light class on <html>
  useEventStream(true) // single WS connection for the whole app
  const { lang } = useTranslation() // Initialize translation hook

  const view = useAppStore((s) => s.currentView)
  const isAuthenticated = useAppStore((s) => s.isAuthenticated)

  useEffect(() => {
    document.title = `LOGIVISION — ${view}`
  }, [view])

  // If not authenticated, show login page
  if (!isAuthenticated) {
    return <LoginPage />
  }

  // Otherwise, show the dashboard
  return (
    <div className="min-h-screen flex flex-col">
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <main className="flex-1 min-w-0 flex flex-col">
          <Header />
          <div className="flex-1 overflow-auto px-6 py-5 dot-grid bg-background/50">
            <PageRouter />
          </div>
        </main>
      </div>
      <StatusBar />
    </div>
  )
}
