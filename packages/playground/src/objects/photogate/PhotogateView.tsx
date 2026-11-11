import type { ObjectViewProps } from '../types'
import { gateReading } from './module'

export function PhotogateView({ wiring }: ObjectViewProps<'photogate', null>) {
  const r = gateReading(wiring)
  return (
    <div className="space-y-1 p-3">
      <div className="flex items-baseline justify-between rounded-lg bg-bg px-3 py-2">
        <span className="text-xs text-muted">Period T</span>
        <span className="font-mono text-2xl font-semibold">{r ? `${r.period.toFixed(3)} s` : '—.——— s'}</span>
      </div>
      <p className="text-xs text-muted">{r ? 'Timing each swing through the gate.' : 'Drag the photogate plug onto the bottom of the swing.'}</p>
    </div>
  )
}
