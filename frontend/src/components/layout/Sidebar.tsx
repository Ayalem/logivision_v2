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
} from 'lucide-react'
import { useMe } from '@/lib/api'
import { useAppStore, type ViewType } from '@/lib/store'
import { useTheme } from '@/hooks/useTheme'
import { cn } from '@/lib/utils'

interface NavItem {
  label: string
  view: ViewType
  icon: typeof LayoutDashboard
  adminOnly?: boolean
}

const NAV: NavItem[] = [
  { label: "Overview", view: 'overview',  icon: LayoutDashboard },
  { label: 'Digital Twin', view: 'zones',     icon: Grid3x3 },
  { label: 'Cameras', view: 'cameras',   icon: Video },
  { label: 'Analytics', view: 'analytics',   icon: BarChart3 },
  { label: 'Alerts', view: 'anomalies', icon: AlertTriangle },
  { label: 'Inventory', view: 'inventory',   icon: Package },
  { label: 'Workforce', view: 'workforce',   icon: Users },
  { label: 'System', view: 'system',    icon: ServerCog, adminOnly: true },
]

export function Sidebar() {
  const view = useAppStore((s) => s.currentView)
  const setView = useAppStore((s) => s.setView)
  const wsState = useAppStore((s) => s.live.wsState)
  const me = useMe()
  const role = me.data?.role ?? 'operator'
  const { isDark, toggle } = useTheme()

  const items = NAV.filter((n) => !n.adminOnly || role === 'admin')

  return (
    <aside className="hidden md:flex w-[200px] shrink-0 flex-col border-r border-border/50 bg-card/30 backdrop-blur-xl overflow-y-auto">
      {/* Logo */}
      <div className="px-4 py-5 flex items-center gap-2.5 border-b border-border/30">
        <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-electric/20 to-teal/20 border border-electric/40 text-electric flex items-center justify-center">
          <Warehouse className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="text-xs font-bold tracking-wider text-gradient">LOGIVISION</div>
          <div className="text-[9px] text-muted-foreground leading-tight">AI</div>
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
              <span className="truncate">{item.label}</span>
              {active && (
                <span className="absolute right-0 top-1/2 -translate-y-1/2 h-3 w-1 bg-gradient-to-b from-electric to-teal rounded-l" />
              )}
            </button>
          )
        })}
      </nav>

      {/* AI Model Status */}
      <div className="px-3 py-4 border-t border-border/30 space-y-3">
        <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">AI Model Status</div>
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
        <div className="space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Pose Estimation</span>
            <span className="font-semibold text-emerald">96%</span>
          </div>
          <div className="h-1 bg-card rounded-full overflow-hidden">
            <div className="h-full w-[96%] bg-gradient-to-r from-emerald to-teal rounded-full" />
          </div>
        </div>
        <div className="space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Path Prediction</span>
            <span className="font-semibold text-emerald">97%</span>
          </div>
          <div className="h-1 bg-card rounded-full overflow-hidden">
            <div className="h-full w-[97%] bg-gradient-to-r from-emerald to-teal rounded-full" />
          </div>
        </div>
        <div className="space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Inference FPS</span>
            <span className="font-semibold text-teal">42.6</span>
          </div>
        </div>
        <div className="space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Latency</span>
            <span className="font-semibold text-teal">23ms</span>
          </div>
        </div>
        <div className="space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Active Streams</span>
            <span className="font-semibold text-teal">24/28</span>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="px-3 py-3 border-t border-border/30 space-y-2">
        <button
          onClick={toggle}
          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-muted-foreground hover:bg-foreground/5 transition-colors"
        >
          {isDark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
          <span>{isDark ? 'Light' : 'Dark'}</span>
        </button>
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
    </aside>
  )
}
