import { Package, AlertTriangle, TrendingUp, TrendingDown, Grid3x3 } from 'lucide-react'
import { useZones, useKpis } from '@/lib/api'
import { cn } from '@/lib/utils'

export function InventoryPage() {
  const { data: zones } = useZones()
  const { data: kpis } = useKpis()

  const zonesList = zones?.zones ?? []

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Inventory</h1>
        <p className="text-xs text-muted-foreground mt-1">Gestion des stocks et des zones</p>
      </div>

      {/* Inventory Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="glass-card rounded-2xl p-4 shadow-soft">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Total en stock</p>
              <p className="text-2xl font-bold text-electric">{kpis?.totalBoxes ?? '—'}</p>
            </div>
            <div className="h-10 w-10 rounded-lg bg-electric/10 flex items-center justify-center">
              <Package className="h-5 w-5 text-electric" />
            </div>
          </div>
        </div>

        <div className="glass-card rounded-2xl p-4 shadow-soft">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Niveau de stock</p>
              <p className="text-2xl font-bold text-emerald">{kpis?.stockLevel ?? '—'}%</p>
            </div>
            <div className="h-10 w-10 rounded-lg bg-emerald/10 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-emerald" />
            </div>
          </div>
        </div>

        <div className="glass-card rounded-2xl p-4 shadow-soft">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Zones critiques</p>
              <p className="text-2xl font-bold text-coral">
                {zonesList.filter(z => z.status === 'critical').length}
              </p>
            </div>
            <div className="h-10 w-10 rounded-lg bg-coral/10 flex items-center justify-center">
              <AlertTriangle className="h-5 w-5 text-coral" />
            </div>
          </div>
        </div>
      </div>

      {/* Zones Overview */}
      <div className="glass-card rounded-2xl shadow-soft overflow-hidden">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <Grid3x3 className="h-4 w-4" />
            Zones de stockage
          </h2>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            {zonesList.length} zones
          </span>
        </div>

        {zonesList.length === 0 ? (
          <div className="p-6 text-xs text-muted-foreground italic">
            Aucune zone configurée
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="border-b border-border/30 bg-card/50">
                <tr>
                  <th className="px-4 py-2 text-left font-semibold text-muted-foreground">Zone</th>
                  <th className="px-4 py-2 text-left font-semibold text-muted-foreground">Type</th>
                  <th className="px-4 py-2 text-left font-semibold text-muted-foreground">Occupation</th>
                  <th className="px-4 py-2 text-left font-semibold text-muted-foreground">Articles</th>
                  <th className="px-4 py-2 text-left font-semibold text-muted-foreground">Capacité</th>
                  <th className="px-4 py-2 text-left font-semibold text-muted-foreground">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/30">
                {zonesList.map((zone) => (
                  <tr key={zone.id} className="hover:bg-foreground/[0.02] transition-colors">
                    <td className="px-4 py-3 font-medium">{zone.name}</td>
                    <td className="px-4 py-3">
                      <span className="text-[10px] uppercase tracking-wider text-muted-foreground px-2 py-1 rounded bg-card/50">
                        {zone.kind}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-24 bg-card rounded-full overflow-hidden">
                          <div
                            className={cn(
                              'h-full rounded-full',
                              zone.occupancy > 80 ? 'bg-coral' : zone.occupancy > 50 ? 'bg-amber' : 'bg-emerald'
                            )}
                            style={{ width: `${zone.occupancy}%` }}
                          />
                        </div>
                        <span className="font-semibold">{zone.occupancy}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">{zone.currentItems}</td>
                    <td className="px-4 py-3">{zone.capacity}</td>
                    <td className="px-4 py-3">
                      <span className={cn(
                        'text-[10px] font-semibold uppercase tracking-wider px-2 py-1 rounded inline-block',
                        zone.status === 'critical' ? 'bg-coral/15 text-coral' :
                        zone.status === 'warning' ? 'bg-amber/15 text-amber' :
                        'bg-emerald/15 text-emerald'
                      )}>
                        {zone.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Zone Categories */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Entry/Exit Zones */}
        <div className="glass-card rounded-2xl p-5 shadow-soft">
          <h2 className="text-sm font-semibold mb-4">Zones d'entrée/sortie</h2>
          <div className="space-y-2">
            {zonesList
              .filter(z => z.kind === 'entry' || z.kind === 'exit')
              .map(zone => (
                <div key={zone.id} className="p-3 rounded-lg bg-card/50 border border-border/30">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium">{zone.name}</p>
                      <p className="text-[10px] text-muted-foreground mt-1">
                        {zone.kind === 'entry' ? 'Entrée' : 'Sortie'} · {zone.currentItems} articles
                      </p>
                    </div>
                    <span className={cn(
                      'text-xs font-semibold uppercase px-2 py-1 rounded',
                      zone.status === 'critical' ? 'bg-coral/15 text-coral' :
                      zone.status === 'warning' ? 'bg-amber/15 text-amber' :
                      'bg-emerald/15 text-emerald'
                    )}>
                      {zone.occupancy}%
                    </span>
                  </div>
                </div>
              ))}
            {zonesList.filter(z => z.kind === 'entry' || z.kind === 'exit').length === 0 && (
              <p className="text-xs text-muted-foreground italic">Aucune zone d'entrée/sortie</p>
            )}
          </div>
        </div>

        {/* Shelf Zones */}
        <div className="glass-card rounded-2xl p-5 shadow-soft">
          <h2 className="text-sm font-semibold mb-4">Rayonnages</h2>
          <div className="space-y-2">
            {zonesList
              .filter(z => z.kind === 'shelf')
              .map(zone => (
                <div key={zone.id} className="p-3 rounded-lg bg-card/50 border border-border/30">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium">{zone.name}</p>
                      <p className="text-[10px] text-muted-foreground mt-1">
                        {zone.currentItems}/{zone.capacity} articles
                      </p>
                    </div>
                    <span className={cn(
                      'text-xs font-semibold uppercase px-2 py-1 rounded',
                      zone.status === 'critical' ? 'bg-coral/15 text-coral' :
                      zone.status === 'warning' ? 'bg-amber/15 text-amber' :
                      'bg-emerald/15 text-emerald'
                    )}>
                      {zone.occupancy}%
                    </span>
                  </div>
                </div>
              ))}
            {zonesList.filter(z => z.kind === 'shelf').length === 0 && (
              <p className="text-xs text-muted-foreground italic">Aucun rayonnage</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
