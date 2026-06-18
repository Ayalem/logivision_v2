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
  const userRole = useAppStore((s) => s.userRole)
  const user = useAppStore((s) => s.user)
  const role = userRole ?? 'worker'
  const { isDark, toggle } = useTheme()
  const logout = useAppStore((s) => s.logout)
  const userName = user?.name ?? (role === 'admin' ? 'Admin' : 'Operator')

  const items = NAV.filter((n) => {
    if (n.adminOnly && role !== 'admin') return false
    if (n.workerOnly && role !== 'worker') return false
    return true
  })

  return (
    <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-border bg-card">
      {/* Brand logo & name */}
      <div className="px-6 py-5 flex items-center gap-3 border-b border-border/30">
        <div className="relative group cursor-pointer" onClick={() => setView('overview')}>
          <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-electric via-electric/80 to-teal border border-white/20 flex items-center justify-center logo-icon-glow overflow-hidden">
            <Warehouse className="h-4 w-4 text-white relative z-10" />
            <div className="absolute inset-0 bg-gradient-to-b from-white/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>
        <div className="flex items-center gap-1 text-sm font-bold tracking-tight text-foreground">
          <span className="logo-shimmer-text">LOGI</span>
          <span className="font-light text-muted-foreground/80">VISION</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-4 space-y-1 flex flex-col overflow-y-auto">
        {items.map((item) => {
          const Icon = item.icon
          const active = view === item.view
          return (
            <button
              key={item.view}
              onClick={() => setView(item.view)}
              className={cn(
                'relative w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all duration-200 text-left text-xs font-semibold',
                active
                  ? 'bg-gradient-to-tr from-electric/15 to-teal/5 text-electric border border-electric/15 shadow-sm shadow-electric/5'
                  : 'text-muted-foreground hover:bg-foreground/5 hover:text-foreground',
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate">{t(item.labelKey)}</span>
              {active && (
                <span className={cn(
                  "absolute top-1/2 -translate-y-1/2 h-5 w-1 bg-gradient-to-b from-electric to-teal rounded-r",
                  lang === 'ar' ? "right-0 rounded-l rounded-r-none" : "left-0 rounded-r"
                )} />
              )}
            </button>
          )
        })}
      </nav>

      {/* Footer Controls */}
      <div className="px-4 py-4 border-t border-border/30 space-y-3 bg-foreground/[0.01]">
        {/* User Info & Profile */}
        <div className="flex items-center justify-between gap-2">
          <button
            onClick={() => setView('profile')}
            className={cn(
              "flex items-center gap-2.5 text-left p-1.5 rounded-xl w-full transition-all border",
              view === 'profile'
                ? "bg-electric/15 border-electric text-electric"
                : "bg-foreground/5 border-border text-muted-foreground hover:bg-foreground/10"
            )}
          >
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-electric/20 to-teal/20 flex items-center justify-center text-electric text-xs font-bold shrink-0">
              {userName.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 pr-1 flex-1">
              <p className="text-xs font-bold leading-none text-foreground truncate">{userName}</p>
              <p className="text-[10px] text-muted-foreground mt-1 capitalize leading-none">{role}</p>
            </div>
          </button>
        </div>

        {/* Theme & Logout Buttons */}
        <div className="flex items-center justify-between gap-2 pt-1">
          <button
            onClick={toggle}
            className="flex-1 h-9 flex items-center justify-center gap-2 rounded-xl text-xs font-semibold text-muted-foreground hover:bg-foreground/5 hover:text-foreground border border-border/50 transition-colors"
          >
            {isDark ? (
              <>
                <Sun className="h-3.5 w-3.5" />
                <span>Clair</span>
              </>
            ) : (
              <>
                <Moon className="h-3.5 w-3.5" />
                <span>Sombre</span>
              </>
            )}
          </button>

          <button
            onClick={() => logout()}
            className="h-9 w-9 flex items-center justify-center rounded-xl text-coral hover:bg-coral/10 border border-coral/20 transition-colors shrink-0"
            title={t('logout')}
          >
            <ArrowLeftRight className="h-4 w-4 rotate-90" />
          </button>
        </div>
      </div>
    </aside>
  )
}
