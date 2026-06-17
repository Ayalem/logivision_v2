import { BarChart3, TrendingUp, Calendar, Download } from 'lucide-react'
import { useKpis, usePredictions } from '@/lib/api'
import { cn } from '@/lib/utils'

export function AnalyticsPage() {
  const { data: kpis } = useKpis()
  const { data: predictions } = usePredictions()

  const congestionForecasts = predictions?.buckets.congestion ?? []

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-xs text-muted-foreground mt-1">Analyse des performances et prédictions</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="flex items-center gap-2 px-3 py-2 rounded-lg bg-card/40 hover:bg-card/60 transition-colors text-xs font-medium">
            <Calendar className="h-4 w-4" />
            <span>7 derniers jours</span>
          </button>
          <button className="p-2 rounded-lg hover:bg-card/60 transition-colors text-muted-foreground hover:text-foreground">
            <Download className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="glass-card rounded-2xl p-4 shadow-soft">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Total de colis</p>
              <p className="text-2xl font-bold text-electric">{kpis?.totalBoxes ?? '—'}</p>
            </div>
            <div className="h-10 w-10 rounded-lg bg-electric/10 flex items-center justify-center">
              <BarChart3 className="h-5 w-5 text-electric" />
            </div>
          </div>
        </div>

        <div className="glass-card rounded-2xl p-4 shadow-soft">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Entrées aujourd'hui</p>
              <p className="text-2xl font-bold text-emerald">{kpis?.todayEntries ?? '—'}</p>
            </div>
            <div className="h-10 w-10 rounded-lg bg-emerald/10 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-emerald" />
            </div>
          </div>
        </div>

        <div className="glass-card rounded-2xl p-4 shadow-soft">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Sorties aujourd'hui</p>
              <p className="text-2xl font-bold text-amber">{kpis?.todayExits ?? '—'}</p>
            </div>
            <div className="h-10 w-10 rounded-lg bg-amber/10 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-amber" />
            </div>
          </div>
        </div>

        <div className="glass-card rounded-2xl p-4 shadow-soft">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Anomalies actives</p>
              <p className="text-2xl font-bold text-coral">{kpis?.activeAnomalies ?? '—'}</p>
            </div>
            <div className="h-10 w-10 rounded-lg bg-coral/10 flex items-center justify-center">
              <BarChart3 className="h-5 w-5 text-coral" />
            </div>
          </div>
        </div>
      </div>

      {/* Performance Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Processing Performance */}
        <div className="glass-card rounded-2xl p-5 shadow-soft">
          <h2 className="text-sm font-semibold mb-4">Performance du système</h2>
          <div className="space-y-3">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-muted-foreground">Temps de traitement moyen</span>
                <span className="text-xs font-semibold text-electric">{kpis?.avgProcessingTime ?? '—'}ms</span>
              </div>
              <div className="h-1.5 bg-card rounded-full overflow-hidden">
                <div className="h-full w-[75%] bg-gradient-to-r from-electric to-teal rounded-full" />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-muted-foreground">Caméras en ligne</span>
                <span className="text-xs font-semibold text-emerald">{kpis?.camerasOnline}/{kpis?.totalCameras}</span>
              </div>
              <div className="h-1.5 bg-card rounded-full overflow-hidden">
                <div className="h-full w-[85%] bg-gradient-to-r from-emerald to-teal rounded-full" />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-muted-foreground">Niveau de stock</span>
                <span className="text-xs font-semibold text-teal">{kpis?.stockLevel ?? '—'}%</span>
              </div>
              <div className="h-1.5 bg-card rounded-full overflow-hidden">
                <div className="h-full w-[60%] bg-gradient-to-r from-teal to-emerald rounded-full" />
              </div>
            </div>
          </div>
        </div>

        {/* System Status */}
        <div className="glass-card rounded-2xl p-5 shadow-soft">
          <h2 className="text-sm font-semibold mb-4">État du système</h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 rounded-lg bg-card/50">
              <span className="text-xs text-muted-foreground">Statut global</span>
              <span className={cn(
                'text-xs font-semibold uppercase px-2 py-1 rounded',
                kpis?.systemStatus === 'operational' ? 'bg-emerald/15 text-emerald' : 'bg-amber/15 text-amber'
              )}>
                {kpis?.systemStatus ?? '—'}
              </span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-lg bg-card/50">
              <span className="text-xs text-muted-foreground">Mode dégradé</span>
              <span className={cn(
                'text-xs font-semibold uppercase px-2 py-1 rounded',
                kpis?.degraded ? 'bg-coral/15 text-coral' : 'bg-emerald/15 text-emerald'
              )}>
                {kpis?.degraded ? 'Actif' : 'Inactif'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Congestion Forecasts */}
      {congestionForecasts.length > 0 && (
        <div className="glass-card rounded-2xl p-5 shadow-soft">
          <h2 className="text-sm font-semibold mb-4">Prédictions de congestion</h2>
          <div className="space-y-2">
            {congestionForecasts.map((forecast) => (
              <div key={forecast.event_id} className="p-3 rounded-lg bg-card/50 border border-border/30">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-medium">{forecast.zone}</p>
                    <p className="text-[10px] text-muted-foreground mt-1">
                      ETA: {forecast.eta_seconds}s · Confiance: {Math.round(forecast.confidence * 100)}%
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-xs font-semibold text-amber">Densité: {Math.round(forecast.density * 100)}%</div>
                    <div className="text-[10px] text-muted-foreground mt-1">
                      {forecast.forecast_source === 'lstm-prsa-v1' ? 'LSTM · PRSA' : 'Règle v0'}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
