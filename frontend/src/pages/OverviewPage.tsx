/**
 * Vue d'ensemble — operator hero matching the dark-navy mockup.
 *
 *  ┌──────────────────────────────────────────────────────────────┐
 *  │  KpiStrip  (5 tiles)                                         │
 *  ├──────────────────────────────────────┬───────────────────────┤
 *  │                                      │ LiveAlertsPanel       │
 *  │   DigitalTwin  (R3F, hero)           │ CongestionPanel       │
 *  │                                      │ AiModelStatus         │
 *  ├──────────────────────────────────────┴───────────────────────┤
 *  │  InsightRail  (narrative AI cards)                            │
 *  ├──────────────────────────────────────────────────────────────┤
 *  │  Caméras · 3 analytical tiles                                 │
 *  └──────────────────────────────────────────────────────────────┘
 */
import { useCameras } from '@/lib/api'
import { AnalyticalCameraFeed } from '@/components/cameras/AnalyticalCameraFeed'
import { KpiStrip } from '@/components/dashboard/KpiStrip'
import { DigitalTwin } from '@/components/digital-twin/DigitalTwin'
import { InsightRail } from '@/components/insights/InsightChain'
import { CongestionPanel } from '@/components/predictions/CongestionPanel'
import { AiModelStatus } from '@/components/predictions/AiModelStatus'
import { LiveAlertsPanel } from '@/components/predictions/LiveAlertsPanel'

export function OverviewPage() {
  const { data: cams } = useCameras()
  const cameras = cams?.cameras ?? []
  return (
    <div className="space-y-5">
      {/* Row 1 — KPI strip (5 tiles) */}
      <KpiStrip />

      {/* Row 2 — Twin (hero) + right rail (Alerts / Congestion / AI Status) */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        <div className="xl:col-span-8 space-y-4">
          <DigitalTwin />
        </div>
        <div className="xl:col-span-4 space-y-4">
          <LiveAlertsPanel />
          <CongestionPanel />
          <AiModelStatus />
        </div>
      </div>

      {/* Row 3 — Insight chain (narrative) */}
      <InsightRail />

      {/* Row 4 — Analytical camera tiles */}
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
