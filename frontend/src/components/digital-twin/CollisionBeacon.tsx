/**
 * Pulsing red torus at each predicted collision point + floating ETA HUD.
 */
import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Billboard, Text } from '@react-three/drei'
import * as THREE from 'three'
import { usePredictions } from '@/lib/api'
import { useAppStore } from '@/lib/store'
import { PALETTE, worldFromNorm } from './twin-config'

function Beacon({ x, y, eta }: { x: number; y: number; eta: number }) {
  const ringRef = useRef<THREE.Mesh>(null)
  const [wx, wz] = worldFromNorm(x, y)
  const reduceMotion = useAppStore((s) => s.reduceMotion)

  useFrame((_, dt) => {
    if (!ringRef.current || reduceMotion) return
    const s = 1 + 0.25 * (1 + Math.sin(performance.now() * 0.006))
    ringRef.current.scale.x = THREE.MathUtils.damp(ringRef.current.scale.x, s, 6, dt)
    ringRef.current.scale.y = ringRef.current.scale.x
    ringRef.current.scale.z = ringRef.current.scale.x
  })

  return (
    <group position={[wx, 0.5, wz]}>
      <mesh ref={ringRef}>
        <torusGeometry args={[0.7, 0.07, 16, 64]} />
        <meshStandardMaterial
          color={PALETTE.collision}
          emissive={PALETTE.collision}
          emissiveIntensity={1.4}
          metalness={0.1}
          roughness={0.4}
          transparent
          opacity={0.9}
        />
      </mesh>
      <Billboard position={[0, 1.4, 0]}>
        <Text
          fontSize={0.4}
          color="#FFFFFF"
          outlineWidth={0.03}
          outlineColor={PALETTE.collision}
          anchorX="center"
          anchorY="middle"
        >
          {`COLLISION · ${eta}s`}
        </Text>
      </Billboard>
    </group>
  )
}

export function CollisionBeacons() {
  const show = useAppStore((s) => s.showCollisions)
  const { data } = usePredictions()
  if (!show || !data) return null
  return (
    <group>
      {data.buckets.collision.map((c) => (
        <Beacon key={c.event_id} x={c.point_x} y={c.point_y} eta={c.eta_seconds} />
      ))}
    </group>
  )
}
