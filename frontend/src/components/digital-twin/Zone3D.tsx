/**
 * One extruded zone polygon on the floor. Click selects, hover lifts.
 */
import { useMemo, useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import { Text } from '@react-three/drei'
import * as THREE from 'three'
import type { Zone } from '@/lib/types'
import { useAppStore } from '@/lib/store'
import {
  FLOOR_SIZE,
  ZONE_HEIGHT,
  colorForOccupancy,
  colorForZoneKind,
  worldFromNorm,
} from './twin-config'

function zoneGeometry(zone: Zone): THREE.ExtrudeGeometry {
  // Build a flat polygon in XZ then extrude along Y.  We construct the
  // 2D shape directly from the normalised polygon then scale to metres.
  const shape = new THREE.Shape()
  zone.polygon.forEach((p, i) => {
    const [x, z] = worldFromNorm(p.x, p.y)
    // Shape works in (x, y) — we treat its y as our world Z.
    if (i === 0) shape.moveTo(x, z)
    else shape.lineTo(x, z)
  })
  const height = ZONE_HEIGHT * (0.3 + (zone.occupancy / 100) * 0.9)
  const geo = new THREE.ExtrudeGeometry(shape, { depth: height, bevelEnabled: false })
  // Lay the shape onto the XZ plane (rotate -90° around X).
  geo.rotateX(-Math.PI / 2)
  return geo
}

export function Zone3D({ zone }: { zone: Zone }) {
  const selected     = useAppStore((s) => s.selectedZone)
  const setSelected  = useAppStore((s) => s.setSelectedZone)
  const reduceMotion = useAppStore((s) => s.reduceMotion)
  const [hovered, setHovered] = useState(false)
  const meshRef = useRef<THREE.Mesh>(null)
  const isSelected = selected === zone.id

  const geometry = useMemo(() => zoneGeometry(zone), [zone])

  const kindColor = colorForZoneKind(zone.kind)
  const occColor  = colorForOccupancy(zone.occupancy)
  const baseColor = zone.kind === 'shelf' ? occColor : kindColor

  useFrame((_, dt) => {
    if (!meshRef.current) return
    const target = (isSelected || hovered) ? 0.25 : 0.0
    meshRef.current.position.y = THREE.MathUtils.damp(meshRef.current.position.y, target, 6, dt)
    // Subtle breathing for entry/exit zones to draw the eye.
    if (!reduceMotion && (zone.kind === 'entry' || zone.kind === 'exit')) {
      const mat = meshRef.current.material as THREE.MeshStandardMaterial
      mat.emissiveIntensity = 0.25 + 0.15 * Math.sin(performance.now() * 0.003)
    }
  })

  // Approximate label position: bbox center in world coords.
  const [labelX, labelZ] = worldFromNorm(
    (zone.x + zone.width / 2) / 100,
    (zone.y + zone.height / 2) / 100,
  )

  return (
    <group>
      <mesh
        ref={meshRef}
        geometry={geometry}
        onPointerOver={(e) => { e.stopPropagation(); setHovered(true); document.body.style.cursor = 'pointer' }}
        onPointerOut={() => { setHovered(false); document.body.style.cursor = 'default' }}
        onClick={(e) => { e.stopPropagation(); setSelected(isSelected ? null : zone.id) }}
        castShadow
        receiveShadow
      >
        <meshStandardMaterial
          color={baseColor}
          emissive={baseColor}
          emissiveIntensity={isSelected ? 0.5 : 0.2}
          metalness={0.2}
          roughness={0.55}
          transparent
          opacity={zone.kind === 'forbidden' ? 0.55 : 0.78}
        />
      </mesh>
      {(hovered || isSelected) && (
        <Text
          position={[labelX, ZONE_HEIGHT + 0.6, labelZ]}
          fontSize={0.5}
          color="#F8FAFC"
          outlineWidth={0.025}
          outlineColor="#0F172A"
          anchorX="center"
          anchorY="middle"
        >
          {zone.name} · {zone.occupancy}%
        </Text>
      )}
    </group>
  )
}

// Floor size export to keep the build tool aware (silences unused warning
// in some bundler configs when ZoneInstances is tree-shaken).
export const _FLOOR_SIZE = FLOOR_SIZE
