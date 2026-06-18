/**
 * Operator overview — every panel is wired to REAL data (no fabricated
 * alerts/timeline/heatmap). Layout: KPI strip → floor map → twin + congestion
 * + live alerts → camera feed + recent-events timeline.
 */
import { useCameras, useAnomalies } from '@/lib/api'
import { AnalyticalCameraFeed } from '@/components/cameras/AnalyticalCameraFeed'
import { KpiStrip } from '@/components/dashboard/KpiStrip'
import { DigitalTwin } from '@/components/digital-twin/DigitalTwin'
import { FloorMap } from '@/components/digital-twin/FloorMap'
import { CongestionPanel } from '@/components/predictions/CongestionPanel'
import { AlertCircle, Activity } from 'lucide-react'

const sevDot: Record<string, string> = {
  critical: 'bg-coral', warning: 'bg-amber', info: 'bg-teal',
}
const sevText: Record<string, string> = {
  critical: 'text-coral', warning: 'text-amber', info: 'text-teal',
}
const fmtTime = (iso: string) => {
  try { return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }
  catch { return '' }
}

export function OverviewPage() {
  const { data: cams } = useCameras()
  const cameras = cams?.cameras ?? []
  const { data: anom } = useAnomalies(12)
  const alerts = anom?.anomalies ?? []

  return (
    <div className="space-y-5">
      <KpiStrip />

      {/* Top-down warehouse floor map + zone detail panel (real zone geometry) */}
      <FloorMap />

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        {/* Left: 3D twin + congestion forecast (both real) */}
        <div className="xl:col-span-2 space-y-4">
          <DigitalTwin />
          <CongestionPanel />
        </div>

        {/* Right: live alerts from the real /api/anomalies stream */}
        <div className="xl:col-span-2">
          <div className="glass-card rounded-xl p-4 border border-border/50 backdrop-blur-xl h-full">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-coral" /> Alertes en direct
              </h3>
              <span className="text-xs text-muted-foreground">{alerts.length} récentes</span>
            </div>
            {alerts.length === 0 ? (
              <div className="h-40 flex items-center justify-center text-xs text-muted-foreground">
                Aucune anomalie — démarrez le pipeline pour des alertes temps réel.
              </div>
            ) : (
              <div className="space-y-2 max-h-[26rem] overflow-y-auto">
                {alerts.slice(0, 10).map((a) => (
                  <div key={a.id} className="flex items-start gap-3 p-2.5 rounded-lg bg-foreground/[0.03] border border-border/40">
                    <div className={`h-2 w-2 rounded-full mt-1.5 flex-shrink-0 ${sevDot[a.severity] ?? 'bg-teal'}`} />
                    <div className="flex-1 min-w-0">
                      <p className={`text-xs font-semibold ${sevText[a.severity] ?? 'text-foreground'}`}>
                        {a.eventType.replace(/_/g, ' ')}
                      </p>
                      <p className="text-[11px] text-muted-foreground truncate">{a.description}</p>
                      <p className="text-[10px] text-muted-foreground">
                        {a.cameraId || a.zone || '—'} · {fmtTime(a.timestamp)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom: live camera feed + recent-events timeline (both real) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          {cameras.length > 0 && <AnalyticalCameraFeed camera={cameras[0]} />}
        </div>
        <div className="glass-card rounded-xl p-4 border border-border/50 backdrop-blur-xl">
          <h3 className="text-sm font-semibold flex items-center gap-2 mb-3">
            <Activity className="h-4 w-4 text-electric" /> Journal des événements
          </h3>
          {alerts.length === 0 ? (
            <p className="text-xs text-muted-foreground py-6 text-center">En attente du pipeline…</p>
          ) : (
            <div className="space-y-1 text-xs max-h-72 overflow-y-auto">
              {alerts.slice(0, 14).map((a) => (
                <div key={a.id} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-foreground/5">
                  <span className="text-muted-foreground font-mono">{fmtTime(a.timestamp)}</span>
                  <span className="text-foreground font-medium truncate px-2 flex-1">{a.eventType.replace(/_/g, ' ')}</span>
                  <span className={sevText[a.severity] ?? 'text-teal'}>●</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
