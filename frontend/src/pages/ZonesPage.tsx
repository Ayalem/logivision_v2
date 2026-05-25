import { MapPin } from 'lucide-react'
import { useZones } from '@/lib/api'
import { useAppStore } from '@/lib/store'
import { cn, formatNumber, getOccupancyColor, getOccupancyLabel } from '@/lib/utils'

export function ZonesPage() {
  const { data } = useZones()
  const zones = data?.zones ?? []
  const selected = useAppStore((s) => s.selectedZone)
  const setSelected = useAppStore((s) => s.setSelectedZone)

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
      {zones.map((z) => {
        const color = getOccupancyColor(z.occupancy)
        const isSelected = selected === z.id
        return (
          <button
            key={z.id}
            onClick={() => setSelected(isSelected ? null : z.id)}
            className={cn(
              'glass-card rounded-2xl p-4 text-left shadow-soft transition-all ring-1',
              isSelected ? 'ring-electric/60' : 'ring-border hover:ring-foreground/20',
            )}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="inline-flex items-center gap-1.5 text-xs font-semibold">
                <MapPin className="h-3.5 w-3.5 text-muted-foreground" />
                {z.name}
              </div>
              <span
                className="text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded"
                style={{ backgroundColor: `${color}1f`, color }}
              >
                {getOccupancyLabel(z.occupancy)}
              </span>
            </div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
              {z.category} · {z.kind}
            </div>
            <div className="h-2 rounded-full bg-muted overflow-hidden mb-2">
              <div className="h-full rounded-full transition-all duration-500" style={{ width: `${z.occupancy}%`, backgroundColor: color }} />
            </div>
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-muted-foreground">
                {formatNumber(z.currentItems)} / {formatNumber(z.capacity)}
              </span>
              <span className="font-bold tabular-nums">{z.occupancy}%</span>
            </div>
          </button>
        )
      })}
    </div>
  )
}
