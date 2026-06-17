/**
 * KPI Strip — top-level metrics dashboard.
 * Displays: Total Orders, Active Forklifts, Inventory Status, Alerts, Efficiency Score, Live Alerts count.
 */
import { 
  TrendingUp as TrendingUpIcon, 
  TrendingDown as TrendingDownIcon, 
  AlertTriangle as AlertTriangleIcon, 
  Package as PackageIcon, 
  Zap as ZapIcon, 
  CheckCircle as CheckCircleIcon 
} from 'lucide-react'
import { useKpis } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/lib/i18n'

interface KpiCardProps {
  icon: React.ReactNode
  label: string
  value: string | number
  unit?: string
  trend?: { direction: 'up' | 'down'; value: number }
  status?: 'normal' | 'warning' | 'critical'
  subtitle?: string
}

function KpiCard({ icon, label, value, unit, trend, status = 'normal', subtitle }: KpiCardProps) {
  const statusColor = {
    normal: 'from-emerald/10 to-teal/5 border-emerald/30',
    warning: 'from-amber/10 to-orange/5 border-amber/30',
    critical: 'from-coral/10 to-red/5 border-coral/30',
  }

  const trendColor = trend?.direction === 'up' ? 'text-emerald' : 'text-coral'
  const trendIcon = trend?.direction === 'up' ? <TrendingUpIcon className="h-3.5 w-3.5" /> : <TrendingDownIcon className="h-3.5 w-3.5" />

  return (
    <div className={cn(
      'glass-card px-4 py-4 rounded-xl border backdrop-blur-xl transition-all duration-200 hover:shadow-lg',
      statusColor[status],
    )}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{label}</span>
            {trend && (
              <div className={cn('flex items-center gap-0.5 text-[10px] font-bold', trendColor)}>
                {trendIcon}
                <span>{trend.value}%</span>
              </div>
            )}
          </div>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-bold text-foreground">{value}</span>
            {unit && <span className="text-xs text-muted-foreground">{unit}</span>}
          </div>
          {subtitle && <p className="text-[10px] text-muted-foreground mt-1">{subtitle}</p>}
        </div>
        <div className="flex-shrink-0 text-muted-foreground">
          {icon}
        </div>
      </div>
    </div>
  )
}

export function KpiStrip() {
  const { t } = useTranslation()
  const { data: kpis } = useKpis()

  const totalOrders = kpis?.totalBoxes ?? 1243
  const activeForklift = kpis ? `${kpis.camerasOnline}/${kpis.totalCameras}` : '23/35'
  const inventoryStatus = kpis?.stockLevel ?? 87
  const alerts = kpis?.activeAnomalies ?? 12
  const efficiencyScore = kpis ? Math.round(Math.max(70, Math.min(100, 100 - kpis.avgProcessingTime / 10))) : 93.4
  const liveAlertsCount = kpis?.activeAnomalies ?? 1

  return (
    <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
      <KpiCard
        icon={<PackageIcon className="h-5 w-5 text-emerald" />}
        label={t('totalOrders')}
        value={totalOrders}
        trend={{ direction: 'up', value: 18 }}
        subtitle="in inventory"
      />
      <KpiCard
        icon={<ZapIcon className="h-5 w-5 text-teal" />}
        label={t('activeForklifts')}
        value={activeForklift}
        trend={{ direction: 'down', value: 5 }}
        subtitle="65% utilization"
      />
      <KpiCard
        icon={<CheckCircleIcon className="h-5 w-5 text-emerald" />}
        label={t('inventoryStatus')}
        value={inventoryStatus}
        unit="%"
        trend={{ direction: 'up', value: 2 }}
        subtitle="vs yesterday"
      />
      <KpiCard
        icon={<AlertTriangleIcon className="h-5 w-5 text-coral" />}
        label={t('alerts')}
        value={alerts}
        trend={{ direction: 'up', value: 8 }}
        status="warning"
        subtitle="active now"
      />
      <KpiCard
        icon={<CheckCircleIcon className="h-5 w-5 text-emerald" />}
        label={t('efficiencyScore')}
        value={efficiencyScore}
        unit="%"
        trend={{ direction: 'up', value: 4 }}
        subtitle="vs yesterday"
      />
      <KpiCard
        icon={<AlertTriangleIcon className="h-5 w-5 text-coral" />}
        label={t('liveAlerts')}
        value={liveAlertsCount}
        status="critical"
        subtitle="View all"
      />
    </div>
  )
}
