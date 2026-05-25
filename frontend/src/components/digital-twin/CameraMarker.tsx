/**
 * Tiny camera mesh sitting above the assigned zone, glowing when online.
 */
import { useMemo } from 'react'
import * as THREE from 'three'
import type { Camera, Zone } from '@/lib/types'
import { PALETTE, worldFromNorm } from './twin-config'

export function CameraMarker({ camera, zones }: { camera: Camera; zones: Zone[] }) {
  const zone = zones.find((z) => z.id === camera.zone)
  if (!zone) return null
  const [wx, wz] = worldFromNorm(
    (zone.x + zone.width / 2) / 100,
    (zone.y + zone.height / 2) / 100,
  )

  const color =
    camera.status === 'online' ? PALETTE.electric : camera.status === 'offline' ? '#475569' : PALETTE.exit

  // FOV cone — short oblique pyramid showing the camera's gaze.
  const coneGeo = useMemo(() => {
    const g = new THREE.ConeGeometry(0.6, 1.4, 16, 1, true)
    g.translate(0, -0.7, 0)
    return g
  }, [])

  return (
    <group position={[wx, 3.2, wz]}>
      <mesh castShadow>
        <boxGeometry args={[0.5, 0.3, 0.5]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.4} roughness={0.4} />
      </mesh>
      <mesh geometry={coneGeo} rotation={[Math.PI / 1.5, 0, 0]}>
        <meshBasicMaterial color={color} transparent opacity={0.18} side={THREE.DoubleSide} />
      </mesh>
    </group>
  )
}
