/**
 * Translucent heatmap plane just above the floor.  Cells from /api/heatmap
 * are rasterised into a 2D canvas with gaussian splats; the canvas becomes
 * a THREE texture applied to a transparent material.
 *
 * Way cheaper than a custom GLSL shader and good enough for the demo.
 */
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useHeatmap } from '@/lib/api'
import { useAppStore } from '@/lib/store'
import { FLOOR_SIZE, HEATMAP_PLANE_Y } from './twin-config'

const TEXTURE_SIZE = 512
const COLOR_STOPS = [
  [0.0,  20,  30,  70,   0],
  [0.25,  6, 182, 212, 110],
  [0.5,  16, 185, 129, 170],
  [0.75, 245, 158, 11, 200],
  [1.0,  239, 68,  68, 230],
] as const

function sampleColor(v: number): [number, number, number, number] {
  for (let i = 1; i < COLOR_STOPS.length; i++) {
    const a = COLOR_STOPS[i - 1]
    const b = COLOR_STOPS[i]
    if (v <= b[0]) {
      const t = (v - a[0]) / Math.max(0.0001, b[0] - a[0])
      return [
        Math.round(a[1] + (b[1] - a[1]) * t),
        Math.round(a[2] + (b[2] - a[2]) * t),
        Math.round(a[3] + (b[3] - a[3]) * t),
        Math.round(a[4] + (b[4] - a[4]) * t),
      ]
    }
  }
  const last = COLOR_STOPS[COLOR_STOPS.length - 1]
  return [last[1], last[2], last[3], last[4]]
}

export function HeatmapLayer() {
  const layer = useAppStore((s) => s.heatmap)
  const { data } = useHeatmap(layer, layer !== 'off')

  // Canvas + texture set up once.
  const { canvas, texture } = useMemo(() => {
    const c = document.createElement('canvas')
    c.width = TEXTURE_SIZE
    c.height = TEXTURE_SIZE
    const t = new THREE.CanvasTexture(c)
    t.colorSpace = THREE.SRGBColorSpace
    t.minFilter = THREE.LinearFilter
    t.magFilter = THREE.LinearFilter
    return { canvas: c, texture: t }
  }, [])

  // Repaint canvas whenever cells change.
  useEffect(() => {
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.clearRect(0, 0, TEXTURE_SIZE, TEXTURE_SIZE)
    if (!data || !data.cells.length) {
      texture.needsUpdate = true
      return
    }
    // Off-screen field accumulating splats.
    const field = new Float32Array(TEXTURE_SIZE * TEXTURE_SIZE)
    const splatRadius = Math.max(12, Math.floor(TEXTURE_SIZE / data.grid / 1.5))
    for (const c of data.cells) {
      const cx = Math.floor(c.x * TEXTURE_SIZE)
      const cy = Math.floor(c.y * TEXTURE_SIZE)
      const v = c.value
      for (let dy = -splatRadius; dy <= splatRadius; dy++) {
        const py = cy + dy
        if (py < 0 || py >= TEXTURE_SIZE) continue
        for (let dx = -splatRadius; dx <= splatRadius; dx++) {
          const px = cx + dx
          if (px < 0 || px >= TEXTURE_SIZE) continue
          const d2 = dx * dx + dy * dy
          const sigma = splatRadius * 0.5
          field[py * TEXTURE_SIZE + px] += v * Math.exp(-d2 / (2 * sigma * sigma))
        }
      }
    }
    let max = 0
    for (let i = 0; i < field.length; i++) if (field[i] > max) max = field[i]
    if (max <= 0) max = 1
    const img = ctx.createImageData(TEXTURE_SIZE, TEXTURE_SIZE)
    for (let i = 0; i < field.length; i++) {
      const v = field[i] / max
      const [r, g, b, a] = sampleColor(v)
      img.data[i * 4] = r
      img.data[i * 4 + 1] = g
      img.data[i * 4 + 2] = b
      img.data[i * 4 + 3] = a
    }
    ctx.putImageData(img, 0, 0)
    texture.needsUpdate = true
  }, [data, canvas, texture])

  useEffect(() => () => texture.dispose(), [texture])

  if (layer === 'off') return null

  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, HEATMAP_PLANE_Y, 0]}>
      <planeGeometry args={[FLOOR_SIZE, FLOOR_SIZE]} />
      <meshBasicMaterial map={texture} transparent depthWrite={false} />
    </mesh>
  )
}
