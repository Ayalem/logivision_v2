/**
 * Operator hero page. Six wow-factor pillars converge here:
 *  KPI strip → 3D Twin (heatmap + trajectories + collisions) → Insight rail
 *           → Congestion panel → Analytical camera tiles.
 */
import { useCameras } from '@/lib/api'
import { AnalyticalCameraFeed } from '@/components/cameras/AnalyticalCameraFeed'
import { KpiStrip } from '@/components/dashboard/KpiStrip'
import { DigitalTwin } from '@/components/digital-twin/DigitalTwin'
import { InsightRail } from '@/components/insights/InsightChain'
import { CongestionPanel } from '@/components/predictions/CongestionPanel'
import { AiModelStatus } from '@/components/predictions/AiModelStatus'

export function OverviewPage() {
  const { data: cams } = useCameras()
  const cameras = cams?.cameras ?? []
  return (
    <div className="space-y-5">
      <KpiStrip />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2 space-y-4">
          <DigitalTwin />
          <CongestionPanel />
        </div>
        <div className="xl:col-span-1 space-y-4">
          <AiModelStatus />
          <InsightRail />
        </div>
      </div>

      <section className="space-y-2">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-semibold">Caméras · vues analytiques</h2>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            {cameras.length} flux
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {cameras.slice(0, 3).map((c) => <AnalyticalCameraFeed key={c.id} camera={c} />)}
        </div>
      </section>
    </div>
  )
}
