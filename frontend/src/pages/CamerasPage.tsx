import { useCameras } from '@/lib/api'
import { AnalyticalCameraFeed } from '@/components/cameras/AnalyticalCameraFeed'

export function CamerasPage() {
  const { data, isLoading } = useCameras()
  const cameras = data?.cameras ?? []
  return (
    <div className="space-y-3">
      <div className="glass-card rounded-2xl p-3 shadow-soft text-xs text-muted-foreground">
        {isLoading ? 'Chargement…' : `${cameras.length} caméras · ${cameras.filter((c) => c.status === 'online').length} en ligne`}
        {data?.degraded && (
          <span className="ml-2 text-amber">(mode dégradé — pipeline Kafka indisponible)</span>
        )}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {cameras.map((c) => <AnalyticalCameraFeed key={c.id} camera={c} />)}
      </div>
    </div>
  )
}
