import { useCameras } from '@/lib/api'
import { AnalyticalCameraFeed } from '@/components/cameras/AnalyticalCameraFeed'

export function CamerasPage() {
  const { data, isLoading } = useCameras()
  const cameras = data?.cameras ?? []
  // Show cameras with a Kafka pipeline ingesting them FIRST — those are
  // the ones with real overlay boxes. Pure feed-only tiles come after.
  const sorted = [...cameras].sort((a, b) => Number(b.kafkaLive) - Number(a.kafkaLive))
  const live = sorted.filter((c) => c.kafkaLive).length

  return (
    <div className="space-y-3">
      <div className="glass-card rounded-2xl p-3 shadow-soft text-xs text-muted-foreground flex flex-wrap items-center gap-4">
        <span>
          {isLoading ? 'Chargement…'
            : `${cameras.length} caméras configurées · ${live} avec pipeline Kafka actif`}
        </span>
        <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald/15 text-emerald font-mono">
          live · kafka
        </span>
        <span className="text-[10px] text-muted-foreground">= flux d'inférence YOLO en cours</span>
        <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-electric/15 text-electric font-mono">
          feed only
        </span>
        <span className="text-[10px] text-muted-foreground">
          = vidéo visible mais le worker ne consomme pas ce flux
        </span>
        {data?.degraded && (
          <span className="ml-auto text-amber">
            (mode dégradé — pipeline Kafka indisponible)
          </span>
        )}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {sorted.map((c) => <AnalyticalCameraFeed key={c.id} camera={c} />)}
      </div>
    </div>
  )
}
