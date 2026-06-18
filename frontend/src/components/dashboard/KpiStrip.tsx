/**
 * KPI Strip — top-level metrics, ALL derived from real Kafka events via
 * GET /api/kpis. No fabricated values, no hardcoded trends: when the
 * pipeline is idle (pipelineActive=false) every tile renders "—" instead of
 * inventing traffic. This is the no-fake-data contract the project requires.
 */
import {
  Boxes as BoxesIcon,
  LogIn as LogInIcon,
  LogOut as LogOutIcon,
  AlertTriangle as AlertTriangleIcon,
  Video as VideoIcon,
  Timer as TimerIcon,
} from 'lucide-react'
import { useKpis } from '@/lib/api'
import { cn } from '@/lib/utils'

interface KpiCardProps {
  icon: React.ReactNode
  label: string
  value: string | number
  unit?: string
  status?: 'normal' | 'warning' | 'critical'
  subtitle?: string
}

function KpiCard({ icon, label, value, unit, status = 'normal', subtitle }: KpiCardProps) {
  const statusColor = {
    normal: 'from-emerald/10 to-teal/5 border-emerald/30',
    warning: 'from-amber/10 to-orange/5 border-amber/30',
    critical: 'from-coral/10 to-red/5 border-coral/30',
  }
  return (
    <div className={cn(
      'glass-card px-4 py-4 rounded-xl border backdrop-blur-xl transition-all duration-200 hover:shadow-lg',
      statusColor[status],
    )}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{label}</span>
          <div className="flex items-baseline gap-1 mt-2">
            <span className="text-2xl font-bold text-foreground">{value}</span>
            {unit && <span className="text-xs text-muted-foreground">{unit}</span>}
          </div>
          {subtitle && <p className="text-[10px] text-muted-foreground mt-1">{subtitle}</p>}
        </div>
        <div className="flex-shrink-0 text-muted-foreground">{icon}</div>
      </div>
    </div>
  )
}

export function KpiStrip() {
  const { data: kpis } = useKpis()
  const live = !!kpis?.pipelineActive
  // "—" whenever the pipeline isn't producing real events.
  const v = (n: number | undefined) => (live && n != null ? n : '—')

  return (
    <>
      {!live && (
        <p className="text-[11px] text-muted-foreground -mb-1">
          Pipeline inactif — démarrez le flux pour des métriques temps réel.
        </p>
      )}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
        <KpiCard icon={<BoxesIcon className="h-5 w-5 text-emerald" />}
          label="Cartons en stock" value={v(kpis?.totalBoxes)} subtitle="entrées − sorties (réel)" />
        <KpiCard icon={<LogInIcon className="h-5 w-5 text-teal" />}
          label="Entrées (jour)" value={v(kpis?.todayEntries)} subtitle="événements entry" />
        <KpiCard icon={<LogOutIcon className="h-5 w-5 text-teal" />}
          label="Sorties (jour)" value={v(kpis?.todayExits)} subtitle="événements exit" />
        <KpiCard icon={<AlertTriangleIcon className="h-5 w-5 text-coral" />}
          label="Anomalies actives" value={v(kpis?.activeAnomalies)}
          status={live && (kpis?.activeAnomalies ?? 0) > 0 ? 'warning' : 'normal'} subtitle="warning + critical" />
        <KpiCard icon={<VideoIcon className="h-5 w-5 text-electric" />}
          label="Caméras en ligne" value={kpis ? `${kpis.camerasOnline}/${kpis.totalCameras}` : '—'}
          subtitle="flux raw-frames < 30 s" />
        <KpiCard icon={<TimerIcon className="h-5 w-5 text-violet" />}
          label="Inférence" value={v(kpis?.avgProcessingTime)} unit="ms" subtitle="latence YOLO moyenne" />
      </div>
    </>
  )
}
