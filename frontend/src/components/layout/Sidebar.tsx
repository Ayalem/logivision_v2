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
  { label: "Vue d'ensemble",  view: 'overview',  icon: LayoutDashboard },
  { label: 'Entrées/Sorties', view: 'entries',   icon: ArrowLeftRight },
  { label: 'Zones',           view: 'zones',     icon: Grid3x3 },
  { label: 'Anomalies',       view: 'anomalies', icon: AlertTriangle },
  { label: 'Caméras',         view: 'cameras',   icon: Video },
  { label: 'Système',         view: 'system',    icon: ServerCog, adminOnly: true },
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
    <aside className="hidden md:flex w-[240px] shrink-0 flex-col border-r border-border bg-card/60 backdrop-blur-xl">
      <div className="px-5 py-5 flex items-center gap-2.5">
        <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-electric/15 to-teal/10 text-electric flex items-center justify-center ring-1 ring-electric/20">
          <Warehouse className="h-[18px] w-[18px]" />
        </div>
        <div className="min-w-0">
          <div className="text-[13px] font-bold tracking-[0.14em] text-gradient">LOGIVISION</div>
          <div className="text-[10px] text-muted-foreground leading-tight">Warehouse Intelligence</div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-2 space-y-0.5">
        {items.map((item) => {
          const Icon = item.icon
          const active = view === item.view
          return (
            <button
              key={item.view}
              onClick={() => setView(item.view)}
              className={cn(
                'relative w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-[13px] font-medium transition-colors text-left',
                active
                  ? 'bg-gradient-to-r from-electric/15 to-teal/5 text-electric'
                  : 'text-muted-foreground hover:bg-foreground/5 hover:text-foreground',
              )}
            >
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-[3px] bg-electric rounded-r" />
              )}
              <Icon className="h-[18px] w-[18px]" />
              <span>{item.label}</span>
              {item.adminOnly && (
                <span className="ml-auto text-[9px] uppercase tracking-wider text-purple">admin</span>
              )}
            </button>
          )
        })}
      </nav>

      <div className="px-4 py-4 border-t border-border space-y-2">
        <button
          onClick={toggle}
          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-muted-foreground hover:bg-foreground/5"
        >
          {isDark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
          {isDark ? 'Mode clair' : 'Mode sombre'}
        </button>
        <div className="text-[11px] text-muted-foreground inline-flex items-center gap-1.5">
          <span className={cn(
            'h-1.5 w-1.5 rounded-full',
            wsState === 'live' ? 'bg-emerald animate-pulse-live'
              : wsState === 'reconnecting' ? 'bg-amber'
              : wsState === 'error' ? 'bg-coral' : 'bg-muted-foreground',
          )} />
          ws · {wsState}
        </div>
        <div className="text-[10px] text-muted-foreground">
          Phase 1 + Phase 2 · <span className="font-mono">{role}</span>
        </div>
      </div>
    </aside>
  )
}
