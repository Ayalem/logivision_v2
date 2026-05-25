/**
 * Animated dashed lines for each track's history → predicted point.
 * Predicted segment uses a contrasting color so the eye reads "future".
 */
import { useMemo } from 'react'
import { Line } from '@react-three/drei'
import { usePredictions } from '@/lib/api'
import { useAppStore } from '@/lib/store'
import { PALETTE, worldFromNorm } from './twin-config'

export function TrajectoryArrows() {
  const show = useAppStore((s) => s.showTrajectories)
  const { data } = usePredictions()

  const lines = useMemo(() => {
    if (!data) return []
    return data.buckets.trajectories.map((t) => {
      const history = t.points.map(
        (p) => {
          const [x, z] = worldFromNorm(p.x, p.y)
          return [x, 0.4, z] as [number, number, number]
        },
      )
      const lastWorld = history[history.length - 1]
      const [px, pz] = worldFromNorm(t.predicted_point.x, t.predicted_point.y)
      const predictedSegment: Array<[number, number, number]> = [
        lastWorld,
        [px, 0.4, pz],
      ]
      return { id: t.event_id, track: t.track_id, history, predictedSegment, speed: t.speed_units_per_s }
    })
  }, [data])

  if (!show || lines.length === 0) return null

  return (
    <group>
      {lines.map((l) => (
        <group key={l.id}>
          {l.history.length >= 2 && (
            <Line
              points={l.history}
              color={PALETTE.trajectory}
              lineWidth={1.5}
              transparent
              opacity={0.85}
            />
          )}
          <Line
            points={l.predictedSegment}
            color={PALETTE.predicted}
            lineWidth={2}
            dashed
            dashSize={0.3}
            gapSize={0.18}
          />
        </group>
      ))}
    </group>
  )
}
