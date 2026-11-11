import { useState } from 'react'
import { cn } from '../../core/cn'
import { forceAt, REGIME_LABEL, regimeAt } from '../forceLab/curve'
import { distanceOf, type ForceLabState } from '../forceLab/module'
import type { CanvasObject, ObjectViewProps } from '../types'

const W = 400
const H = 190
const CHART = { x: 44, y: 12, w: 340, h: 140 }
const F_MIN = -8
const F_MAX = 20

export function ForceReadoutView({ peers }: ObjectViewProps<'force-readout', null>) {
  const [showCurve, setShowCurve] = useState(false)
  const lab = peers.find((p): p is CanvasObject<'force-lab', ForceLabState> => p.type === 'force-lab')
  if (!lab) return <p className="p-3 text-sm text-muted">No force lab in this experiment.</p>

  const { curve, range, forceUnit } = lab.config
  const r = distanceOf(lab.state)
  const f = forceAt(curve, r)
  const regime = regimeAt(curve, r)
  const xOf = (x: number) => CHART.x + ((x - range[0]) / (range[1] - range[0])) * CHART.w
  const yOf = (y: number) => CHART.y + ((F_MAX - Math.max(F_MIN, Math.min(F_MAX, y))) / (F_MAX - F_MIN)) * CHART.h
  const full: string[] = []
  if (showCurve) for (let x = range[0]; x <= range[1] + 1e-9; x += 0.004) full.push(`${xOf(x).toFixed(1)},${yOf(forceAt(curve, x)).toFixed(1)}`)
  const ticks = [range[0], 0.4, 0.6, 0.8, 1.0, range[1]].filter((t, i, all) => t <= range[1] && all.indexOf(t) === i)

  return (
    <div className="flex flex-col gap-2 p-3">
      <div className="grid grid-cols-3 gap-2 text-center">
        <Stat label="Distance r" value={`${r.toFixed(3)} nm`} />
        <Stat label={`Net force (${forceUnit})`} value={`${f > 0 ? '+' : ''}${Math.abs(f) >= 100 ? f.toFixed(0) : f.toFixed(2)}`} />
        <div className="rounded-lg border border-line px-2 py-1.5">
          <p className="text-[10px] text-muted">State</p>
          <p
            className={cn(
              'text-sm font-semibold',
              regime === 'repulsive' && 'text-bad',
              regime === 'balanced' && 'text-good',
              regime === 'attractive' && 'text-accent',
              regime === 'negligible' && 'text-muted',
            )}
          >
            {REGIME_LABEL[regime]}
          </p>
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded-lg border border-line bg-bg">
        <rect x={CHART.x} y={CHART.y} width={CHART.w} height={CHART.h} className="fill-surface stroke-line" />
        <line x1={CHART.x} x2={CHART.x + CHART.w} y1={yOf(0)} y2={yOf(0)} className="stroke-muted" strokeDasharray="4 3" />
        <text x={CHART.x - 6} y={CHART.y + 10} textAnchor="end" className="fill-bad text-[10px]">
          push
        </text>
        <text x={CHART.x - 6} y={CHART.y + CHART.h - 2} textAnchor="end" className="fill-accent text-[10px]">
          pull
        </text>
        <text x={CHART.x - 6} y={yOf(0) + 3} textAnchor="end" className="fill-muted text-[10px]">
          0
        </text>
        {ticks.map((t) => (
          <text key={t} x={xOf(t)} y={CHART.y + CHART.h + 14} textAnchor="middle" className="fill-muted font-mono text-[10px]">
            {t.toFixed(2)}
          </text>
        ))}
        <text x={CHART.x + CHART.w} y={CHART.y + CHART.h + 30} textAnchor="end" className="fill-muted text-[10px]">
          r / nm
        </text>
        {showCurve && <polyline points={full.join(' ')} className="fill-none stroke-muted" strokeWidth={1.5} />}
        {lab.state.trail.map((v) => (
          <circle key={v} cx={xOf(v)} cy={yOf(forceAt(curve, v))} r={1.8} className={forceAt(curve, v) > 0 ? 'fill-bad/60' : 'fill-accent/60'} />
        ))}
        <line x1={xOf(r)} x2={xOf(r)} y1={CHART.y} y2={CHART.y + CHART.h} className="stroke-accent/40" />
        <circle cx={xOf(r)} cy={yOf(f)} r={5} className={cn('stroke-surface', f > 0 ? 'fill-bad' : 'fill-accent')} strokeWidth={2} />
        {f > F_MAX && (
          <text x={xOf(r) + 8} y={CHART.y + 12} className="fill-bad text-[10px]">
            ↑ off chart
          </text>
        )}
      </svg>

      <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted">
        <input type="checkbox" checked={showCurve} onChange={(e) => setShowCurve(e.target.checked)} />
        Show the full curve (otherwise only the distances you have tried)
      </label>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line px-2 py-1.5">
      <p className="truncate text-[10px] text-muted">{label}</p>
      <p className="font-mono text-sm font-semibold">{value}</p>
    </div>
  )
}
