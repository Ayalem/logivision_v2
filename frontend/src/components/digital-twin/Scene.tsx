/**
 * Scene composition: lights, camera, floor, walls, zones, overlays.
 */
import { Grid, OrbitControls } from '@react-three/drei'
import { useCameras, useZones } from '@/lib/api'
import { CameraMarker } from './CameraMarker'
import { CollisionBeacons } from './CollisionBeacon'
import { HeatmapLayer } from './HeatmapLayer'
import { TrajectoryArrows } from './TrajectoryArrows'
import { Zone3D } from './Zone3D'
import { FLOOR_SIZE, PALETTE, WALL_HEIGHT } from './twin-config'

function Walls() {
  const half = FLOOR_SIZE / 2
  const t = 0.2
  return (
    <group>
      {/* 4 thin walls + a roof gridded with beams */}
      <mesh position={[0, WALL_HEIGHT / 2, -half]} castShadow receiveShadow>
        <boxGeometry args={[FLOOR_SIZE, WALL_HEIGHT, t]} />
        <meshStandardMaterial color={PALETTE.wall} metalness={0.1} roughness={0.7} />
      </mesh>
      <mesh position={[0, WALL_HEIGHT / 2, half]} castShadow receiveShadow>
        <boxGeometry args={[FLOOR_SIZE, WALL_HEIGHT, t]} />
        <meshStandardMaterial color={PALETTE.wall} metalness={0.1} roughness={0.7} />
      </mesh>
      <mesh position={[-half, WALL_HEIGHT / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[t, WALL_HEIGHT, FLOOR_SIZE]} />
        <meshStandardMaterial color={PALETTE.wall} metalness={0.1} roughness={0.7} />
      </mesh>
      <mesh position={[half, WALL_HEIGHT / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[t, WALL_HEIGHT, FLOOR_SIZE]} />
        <meshStandardMaterial color={PALETTE.wall} metalness={0.1} roughness={0.7} />
      </mesh>
      {/* Roof beams */}
      {Array.from({ length: 5 }, (_, i) => (
        <mesh key={i} position={[0, WALL_HEIGHT - 0.1, -half + (i + 1) * (FLOOR_SIZE / 6)]}>
          <boxGeometry args={[FLOOR_SIZE, 0.12, 0.18]} />
          <meshStandardMaterial color="#0F172A" metalness={0.6} roughness={0.4} />
        </mesh>
      ))}
    </group>
  )
}

export function Scene() {
  const zonesQ = useZones()
  const camsQ = useCameras()
  const zones = zonesQ.data?.zones ?? []
  const cameras = camsQ.data?.cameras ?? []

  return (
    <>
      <color attach="background" args={[PALETTE.floor]} />
      <fog attach="fog" args={[PALETTE.floor, 22, 50]} />

      <ambientLight intensity={0.45} />
      <directionalLight
        position={[8, 14, 6]}
        intensity={1.2}
        castShadow
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
      />
      <pointLight position={[0, 8, 0]} intensity={0.8} color="#06B6D4" />

      <OrbitControls
        enableDamping
        dampingFactor={0.08}
        minDistance={8}
        maxDistance={40}
        maxPolarAngle={Math.PI / 2.1}
        target={[0, 1, 0]}
      />

      {/* Floor */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[FLOOR_SIZE, FLOOR_SIZE]} />
        <meshStandardMaterial color={PALETTE.floor} roughness={0.9} metalness={0.05} />
      </mesh>
      <Grid
        args={[FLOOR_SIZE, FLOOR_SIZE]}
        cellColor={PALETTE.floorGrid}
        sectionColor="#334155"
        sectionThickness={1}
        cellThickness={0.5}
        fadeDistance={28}
        fadeStrength={1}
        infiniteGrid={false}
        position={[0, 0.001, 0]}
      />

      <HeatmapLayer />
      <Walls />

      {zones.map((z) => (
        <Zone3D key={z.id} zone={z} />
      ))}

      {cameras.map((c) => (
        <CameraMarker key={c.id} camera={c} zones={zones} />
      ))}

      <TrajectoryArrows />
      <CollisionBeacons />
    </>
  )
}
