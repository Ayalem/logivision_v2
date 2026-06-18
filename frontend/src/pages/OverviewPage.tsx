/**
 * Operator hero page — comprehensive warehouse dashboard.
 * Layout: KPI strip → 3-column hero (Digital Twin + Alerts/Predictions) → Camera feed + Activity Timeline + Heatmap
 */
import { useCameras } from '@/lib/api'
import { AnalyticalCameraFeed } from '@/components/cameras/AnalyticalCameraFeed'
import { KpiStrip } from '@/components/dashboard/KpiStrip'
import { DigitalTwin } from '@/components/digital-twin/DigitalTwin'
import { CongestionPanel } from '@/components/predictions/CongestionPanel'
import { AlertCircle, TrendingUp, Activity } from 'lucide-react'
import { useTranslation } from '@/lib/i18n'

export function OverviewPage() {
  const { t } = useTranslation()
  const { data: cams } = useCameras()
  const cameras = cams?.cameras ?? []

  return (
    <div className="space-y-5">
      {/* Top KPI Strip */}
      <KpiStrip />

      {/* Hero Section: 3-column layout */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        {/* Left: Digital Twin (2 columns) */}
        <div className="xl:col-span-2 space-y-4">
          <DigitalTwin />
          <CongestionPanel />
        </div>

        {/* Right: Live Alerts & Predictions (1 column) */}
        <div className="xl:col-span-2 space-y-4">
          {/* Live Alerts Panel */}
          <div className="bg-card rounded-xl p-4 border border-border interactive-card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-foreground">
                <AlertCircle className="h-4 w-4 text-coral" />
                {t('liveAlerts')}
              </h3>
              <span className="text-xs font-semibold text-electric cursor-pointer hover:underline">View all</span>
            </div>
            <div className="space-y-2">
              {/* Alert Item 1 */}
              <div className="flex items-start gap-3 p-3 rounded-lg border border-border border-l-4 border-l-coral bg-coral/5">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-coral">POTENTIAL COLLIDER</span>
                    <span className="text-[9px] font-semibold text-muted-foreground">16:32:10</span>
                  </div>
                  <p className="text-xs font-semibold text-foreground mt-1">Forklift #07 & #14</p>
                  <p className="text-[10px] text-muted-foreground">Aisle B</p>
                </div>
              </div>
              {/* Alert Item 2 */}
              <div className="flex items-start gap-3 p-3 rounded-lg border border-border border-l-4 border-l-amber bg-amber/5">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-amber">UNAUTHORIZED AREA</span>
                    <span className="text-[9px] font-semibold text-muted-foreground">16:13:48</span>
                  </div>
                  <p className="text-xs font-semibold text-foreground mt-1">Worker #1 detected</p>
                  <p className="text-[10px] text-muted-foreground">Zone D - Restricted Area</p>
                </div>
              </div>
              {/* Alert Item 3 */}
              <div className="flex items-start gap-3 p-3 rounded-lg border border-border border-l-4 border-l-amber bg-amber/5">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-amber">SPEED VIOLATION</span>
                    <span className="text-[9px] font-semibold text-muted-foreground">16:13:42</span>
                  </div>
                  <p className="text-xs font-semibold text-foreground mt-1">Forklift #03</p>
                  <p className="text-[10px] text-muted-foreground">Speed: 8.2 km/h</p>
                </div>
              </div>
              {/* Alert Item 4 */}
              <div className="flex items-start gap-3 p-3 rounded-lg border border-border border-l-4 border-l-teal bg-teal/5">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-teal">PALLET LEFT IN AISLE</span>
                    <span className="text-[9px] font-semibold text-muted-foreground">16:13:21</span>
                  </div>
                  <p className="text-xs font-semibold text-foreground mt-1">Pallet obstruction</p>
                  <p className="text-[10px] text-muted-foreground">Aisle C - Block C3</p>
                </div>
              </div>
            </div>
          </div>

          {/* Predictions Panel */}
          <div className="bg-card rounded-xl p-4 border border-border interactive-card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-foreground">
                <TrendingUp className="h-4 w-4 text-electric" />
                Predictions
              </h3>
            </div>
            <div className="space-y-4">
              {/* Prediction 1 */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold text-foreground">Congestion Risk</span>
                    <span className="text-[10px] text-muted-foreground block">Aisle C</span>
                  </div>
                  <span className="text-xs font-bold text-coral">91%</span>
                </div>
                <div className="h-2 bg-secondary rounded-full overflow-hidden relative">
                  <div className="h-full w-[91%] bg-gradient-to-r from-coral to-amber rounded-full relative overflow-hidden">
                    <div className="absolute inset-0 progress-shimmer" />
                  </div>
                </div>
              </div>
              {/* Prediction 2 */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold text-foreground">Inventory Depletion</span>
                    <span className="text-[10px] text-muted-foreground block">Item #1042 - Zone B - 2h 42m</span>
                  </div>
                  <span className="text-xs font-bold text-teal">55%</span>
                </div>
                <div className="h-2 bg-secondary rounded-full overflow-hidden relative">
                  <div className="h-full w-[55%] bg-gradient-to-r from-teal to-emerald rounded-full relative overflow-hidden">
                    <div className="absolute inset-0 progress-shimmer" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Section: Camera Feed + Activity Timeline + Heatmap */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Camera Feed */}
        <div className="lg:col-span-1">
          {cameras.length > 0 && (
            <AnalyticalCameraFeed camera={cameras[0]} />
          )}
        </div>

        {/* Activity Timeline */}
        <div className="lg:col-span-1 glass-card rounded-xl p-4 border border-border/50 backdrop-blur-xl interactive-card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Activity className="h-4 w-4 text-electric" />
              Activity Timeline
            </h3>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between py-2 px-2 rounded hover:bg-foreground/5">
              <span className="text-muted-foreground">14:10</span>
              <span className="text-foreground font-medium">Forklift #01</span>
              <span className="text-emerald">✓</span>
            </div>
            <div className="flex items-center justify-between py-2 px-2 rounded hover:bg-foreground/5">
              <span className="text-muted-foreground">14:15</span>
              <span className="text-foreground font-medium">Aisle B</span>
              <span className="text-emerald">✓</span>
            </div>
            <div className="flex items-center justify-between py-2 px-2 rounded hover:bg-foreground/5">
              <span className="text-muted-foreground">14:20</span>
              <span className="text-foreground font-medium">Forklift #14</span>
              <span className="text-emerald">✓</span>
            </div>
            <div className="flex items-center justify-between py-2 px-2 rounded hover:bg-foreground/5">
              <span className="text-muted-foreground">14:25</span>
              <span className="text-foreground font-medium">Aisle A</span>
              <span className="text-emerald">✓</span>
            </div>
            <div className="flex items-center justify-between py-2 px-2 rounded hover:bg-foreground/5">
              <span className="text-muted-foreground">14:30</span>
              <span className="text-foreground font-medium">Forklift #03</span>
              <span className="text-coral">⚠</span>
            </div>
          </div>
        </div>

        {/* Heatmap */}
        <div className="lg:col-span-1 glass-card rounded-xl p-4 border border-border/50 backdrop-blur-xl interactive-card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold">Heatmap - Forklift Activity</h3>
          </div>
          <div className="w-full h-32 bg-gradient-to-br from-blue-900 via-purple-900 to-red-900 rounded-lg relative overflow-hidden">
            <div className="absolute inset-0 opacity-60">
              <div className="absolute top-1/4 left-1/3 w-12 h-12 bg-red-500 rounded-full blur-2xl" />
              <div className="absolute top-1/2 right-1/4 w-16 h-16 bg-yellow-500 rounded-full blur-3xl" />
              <div className="absolute bottom-1/4 left-1/4 w-10 h-10 bg-cyan-400 rounded-full blur-2xl" />
            </div>
          </div>
          <div className="flex items-center justify-between mt-3 text-xs">
            <span className="text-muted-foreground">Low</span>
            <div className="flex gap-1">
              <div className="h-2 w-2 rounded-full bg-blue-600" />
              <div className="h-2 w-2 rounded-full bg-cyan-500" />
              <div className="h-2 w-2 rounded-full bg-yellow-500" />
              <div className="h-2 w-2 rounded-full bg-red-500" />
            </div>
            <span className="text-muted-foreground">High</span>
          </div>
        </div>
      </div>
    </div>
  )
}
