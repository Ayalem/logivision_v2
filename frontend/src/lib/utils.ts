import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

/** Compact number formatter (1234 → "1.2K", 1234567 → "1.2M"). */
export function formatNumber(num: number): string {
  if (Math.abs(num) >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`
  if (Math.abs(num) >= 1_000) return `${(num / 1_000).toFixed(1)}K`
  return num.toLocaleString('fr-FR')
}

export function formatTime(date: Date | string | number): string {
  return new Date(date).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

export function formatRelativeFR(date: Date | string | number): string {
  const ms = typeof date === 'number' ? date : new Date(date).getTime()
  const diff = Math.floor((Date.now() - ms) / 1000)
  if (diff < 5) return "à l'instant"
  if (diff < 60) return `il y a ${diff}s`
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)}h`
  return `il y a ${Math.floor(diff / 86400)}j`
}

/** Bucket an occupancy % into a brand color. Critical/elevated/moderate/normal.
 *  `null` (no real snapshot yet) renders neutral slate. */
export function getOccupancyColor(occupancy: number | null): string {
  if (occupancy === null) return '#64748B'
  if (occupancy >= 90) return '#EF4444'
  if (occupancy >= 70) return '#F59E0B'
  if (occupancy >= 50) return '#06B6D4'
  return '#10B981'
}

export function getOccupancyLabel(occupancy: number | null): string {
  if (occupancy === null) return 'En attente'
  if (occupancy >= 90) return 'Critique'
  if (occupancy >= 70) return 'Élevé'
  if (occupancy >= 50) return 'Modéré'
  return 'Normal'
}
