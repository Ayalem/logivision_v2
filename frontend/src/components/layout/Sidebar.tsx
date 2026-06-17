import {
  Activity,
  AlertTriangle,
  ArrowLeftRight,
  Grid3x3,
  LayoutDashboard,
  Moon,
  ServerCog,
  Sun,
  Video,
  Warehouse,
  BarChart3,
  Users,
  Package,
  Settings,
  LineChart as ChartDots3,
  History,
  CheckSquare,
  Eye,
  Zap,
} from 'lucide-react'
import { useAppStore, type ViewType } from '@/lib/store'
import { useTheme } from '@/hooks/useTheme'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/lib/i18n'
import { useMe } from '@/lib/api'

interface NavItem {
  labelKey: any // Using any to avoid TS issues with i18n keys for now
  view: ViewType
  icon: typeof LayoutDashboard
  adminOnly?: boolean
  workerOnly?: boolean
}

const NAV: NavItem[] = [
  { labelKey: "overview", view: 'overview',  icon: LayoutDashboard },
  { labelKey: 'digitalTwin', view: 'zones',     icon: Grid3x3, adminOnly: true },
  { labelKey: 'cameras', view: 'cameras',   icon: Video },
  { labelKey: 'analytics', view: 'analytics',   icon: BarChart3, adminOnly: true },
  { labelKey: 'alerts', view: 'anomalies', icon: AlertTriangle },
  { labelKey: 'inventory', view: 'inventory',   icon: Package },
  { labelKey: 'workforce', view: 'workforce',   icon: Users },
  { labelKey: 'myTasks', view: 'tasks', icon: CheckSquare },
  { labelKey: 'activityLog', view: 'activity-log', icon: History, adminOnly: true },
  { labelKey: 'mlMonitoring', view: 'ml-monitoring', icon: ChartDots3, adminOnly: true },
  { labelKey: 'system', view: 'system',    icon: ServerCog, adminOnly: true },
  { labelKey: 'settings', view: 'settings', icon: Settings },
]

export function Sidebar() {
  const { t, lang } = useTranslation()
  const view = useAppStore((s) => s.currentView)
  const setView = useAppStore((s) => s.setView)
  const wsState = useAppStore((s) => s.live.wsState)
  const userRole = useAppStore((s) => s.userRole)
  const role = userRole ?? 'worker'
  const { isDark, toggle } = useTheme()
  const logout = useAppStore((s) => s.logout)
  const me = useMe()
  const userName = me.data?.name ?? (role === 'admin' ? 'Admin' : 'Operator')

  const items = NAV.filter((n) => {
    if (n.adminOnly && role !== 'admin') return false
    if (n.workerOnly && role !== 'worker') return false
    return true
  })

  return (
    <aside className="hidden md:flex w-[200px] shrink-0 flex-col border-r border-border/50 bg-card/30 backdrop-blur-xl overflow-y-auto">
      {/* Logo */}
      <div className="px-5 py-6 flex items-center gap-3 border-b border-border/30 group cursor-default">
        <div className="relative">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-electric via-electric/80 to-teal border border-white/20 flex items-center justify-center logo-icon-glow overflow-hidden">
            <Warehouse className="h-5 w-5 text-white relative z-10" />
            <div className="absolute inset-0 bg-gradient-to-b from-white/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
          <div className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-background border-2 border-card flex items-center justify-center">
            <Zap className="h-2 w-2 text-amber fill-amber animate-pulse" />
          </div>
        </div>
        <div className="min-w-0 flex flex-col">
          <div className="flex items-center gap-1">
            <span className="text-sm font-black tracking-tighter logo-shimmer-text">LOGI</span>
            <span className="text-sm font-light tracking-widest text-foreground/80">VISION</span>
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <div className="h-1 w-1 rounded-full bg-emerald" />
            <span className="text-[8px] font-bold uppercase tracking-[0.2em] text-muted-foreground/60">Intelligence</span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-3 space-y-1">
        {items.map((item) => {
          const Icon = item.icon
          const active = view === item.view
          return (
            <button
              key={item.view}
              onClick={() => setView(item.view)}
              className={cn(
                'relative w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-xs font-medium transition-all duration-200 text-left',
                active
                  ? 'bg-gradient-to-r from-electric/20 to-teal/10 text-electric border border-electric/30 shadow-lg shadow-electric/10'
                  : 'text-muted-foreground hover:bg-foreground/5 hover:text-foreground',
              )}
            >
              <Icon className="h-4 w-4 flex-shrink-0" />
              <span className="truncate">{t(item.labelKey)}</span>
              {active && (
                <span className={cn(
                  "absolute top-1/2 -translate-y-1/2 h-3 w-1 bg-gradient-to-b from-electric to-teal rounded-l",
                  lang === 'ar' ? "left-0 rounded-r rounded-l-none" : "right-0 rounded-l"
                )} />
              )}
            </button>
          )
        })}
      </nav>

      {/* AI Model Status */}
      <div className="px-3 py-4 border-t border-border/30 space-y-3">
        <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{t('systemStatus')}</div>
        <div className="space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Object Detection</span>
            <span className="font-semibold text-emerald">98%</span>
          </div>
          <div className="h-1 bg-card rounded-full overflow-hidden">
            <div className="h-full w-[98%] bg-gradient-to-r from-emerald to-teal rounded-full" />
          </div>
        </div>
        <div className="space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Tracking</span>
            <span className="font-semibold text-emerald">97%</span>
          </div>
          <div className="h-1 bg-card rounded-full overflow-hidden">
            <div className="h-full w-[97%] bg-gradient-to-r from-emerald to-teal rounded-full" />
          </div>
        </div>
        <div className="space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Anomaly Detection</span>
            <span className="font-semibold text-amber">95%</span>
          </div>
          <div className="h-1 bg-card rounded-full overflow-hidden">
            <div className="h-full w-[95%] bg-gradient-to-r from-amber to-coral rounded-full" />
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="px-3 py-3 border-t border-border/30 space-y-1.5">
        <button
          onClick={() => setView('profile')}
          className={cn(
            "w-full flex items-center gap-2 px-2 py-2 rounded-lg text-xs font-medium transition-all",
            view === 'profile' ? "bg-electric/10 text-electric" : "text-muted-foreground hover:bg-foreground/5"
          )}
        >
          <div className="h-5 w-5 rounded-md bg-gradient-to-br from-electric/20 to-teal/20 flex items-center justify-center text-[10px] font-bold text-electric">
            {userName.charAt(0).toUpperCase()}
          </div>
          <span className="truncate">{userName}</span>
        </button>

        <button
          onClick={toggle}
          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-muted-foreground hover:bg-foreground/5 transition-colors"
        >
          {isDark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
          <span>{isDark ? 'Mode' : 'Mode'}</span>
        </button>

        <button
          onClick={() => logout()}
          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-coral hover:bg-coral/10 transition-colors mt-1"
        >
          <ArrowLeftRight className="h-3.5 w-3.5 rotate-90" />
          <span>{t('logout')}</span>
        </button>

        <div className="pt-2 flex items-center justify-between">
          <div className="text-[9px] text-muted-foreground inline-flex items-center gap-1.5">
            <span className={cn(
              'h-1.5 w-1.5 rounded-full',
              wsState === 'live' ? 'bg-emerald animate-pulse'
                : wsState === 'reconnecting' ? 'bg-amber'
                : wsState === 'error' ? 'bg-coral' : 'bg-muted-foreground',
            )} />
            <span>ws · {wsState}</span>
          </div>
          <div className="text-[8px] text-muted-foreground">
            <span className="font-mono">{role}</span>
          </div>
        </div>
      </div>
    </aside>
  )
}
