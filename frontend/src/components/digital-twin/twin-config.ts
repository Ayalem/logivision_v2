/**
 * Shared constants + coordinate helpers for the R3F warehouse twin.
 *
 * Backend zone coords are normalised (x, y) ∈ [0, 1] with origin top-left
 * (image convention).  The 3D scene lives in the X/Z plane (Y is up).
 * `worldFromNorm` maps the backend's 0..1 to a centered floor in metres.
 */

export const FLOOR_SIZE = 20      // metres per side
export const WALL_HEIGHT = 5
export const ZONE_HEIGHT = 0.8    // extrusion of zone polygons (visual only)
export const HEATMAP_PLANE_Y = 0.02  // just above the floor to avoid z-fighting

export const PALETTE = {
  floor:        '#0F172A',
  floorGrid:    '#1E293B',
  wall:         '#1E293B',
  rack:         '#334155',
  shelf:        '#06B6D4',
  entry:        '#10B981',
  exit:         '#F59E0B',
  forbidden:    '#EF4444',
  electric:     '#2563EB',
  trajectory:   '#06B6D4',
  predicted:    '#8B5CF6',
  collision:    '#EF4444',
} as const

/** Map a normalised (x, y) ∈ [0,1] (origin top-left) to a world (X, Z) point. */
export function worldFromNorm(x: number, y: number): [number, number] {
  return [(x - 0.5) * FLOOR_SIZE, (y - 0.5) * FLOOR_SIZE]
}

/** Color for a zone based on its `kind`. */
export function colorForZoneKind(kind: string): string {
  if (kind === 'entry') return PALETTE.entry
  if (kind === 'exit') return PALETTE.exit
  if (kind === 'forbidden') return PALETTE.forbidden
  return PALETTE.shelf
}

/** Color for occupancy bucket. `null` (no real snapshot yet) → slate. */
export function colorForOccupancy(pct: number | null): string {
  if (pct === null) return '#64748B'
  if (pct >= 90) return '#EF4444'
  if (pct >= 70) return '#F59E0B'
  if (pct >= 50) return '#06B6D4'
  return '#10B981'
}
