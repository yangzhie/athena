import { useState } from 'react'
import { cn } from '../../core/cn'
import { colourLevel, colourName, pHAfter, titrantFromReading } from '../titration/chemistry'
import { bulkPH, type TitrationState } from '../titration/module'
import type { CanvasObject, ObjectViewProps } from '../types'

const W = 420
const H = 200
const CHART = { x: 36, y: 10, w: 370, h: 150 }

export function TitrationReadoutView({ peers }: ObjectViewProps<'titration-readout', null>) {
  const [showCurve, setShowCurve] = useState(false)
  const rig = peers.find((p): p is CanvasObject<'titration', TitrationState> => p.type === 'titration')
  if (!rig) return <p className="p-3 text-sm text-muted">No titration rig in this experiment.</p>

  const config = rig.config
  const s = rig.state
  const pH = bulkPH(config, s)
  const colour = colourName(colourLevel(config, pH))
  const vMax = Math.min(config.burette.capacity, 40)
  const xOf = (v: number) => CHART.x + (Math.min(v, vMax) / vMax) * CHART.w
  const yOf = (p: number) => CHART.y + ((14 - p) / 14) * CHART.h
  const full: string[] = []
  if (showCurve) for (let v = 0; v <= vMax + 1e-9; v += 0.1) full.push(`${xOf(v).toFixed(1)},${yOf(pHAfter(config, v)).toFixed(1)}`)
  const [lo, hi] = config.indicator.transition

  return (
    <div className="flex flex-col gap-2 p-3 text-sm">
      <div className="grid grid-cols-3 gap-2 text-center">
        <Stat label="Burette reading" value={`${s.volume.toFixed(2)} mL`} />
        <Stat label="pH (mixed, simulated probe)" value={pH.toFixed(2)} />
        <div className="rounded-lg border border-line px-2 py-1.5">
          <p className="text-[10px] text-muted">Flask colour</p>
          <p className={cn('text-sm font-semibold', colour === 'colourless' ? 'text-muted' : 'text-pink-500')}>{colour}</p>
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded-lg border border-line bg-bg">
        <rect x={CHART.x} y={CHART.y} width={CHART.w} height={CHART.h} className="fill-surface stroke-line" />
        <rect x={CHART.x} y={yOf(hi)} width={CHART.w} height={yOf(lo) - yOf(hi)} className="fill-pink-500/10" />
        <text x={CHART.x + CHART.w - 4} y={yOf(hi) + 10} textAnchor="end" className="fill-pink-500 text-[9px]">
          {config.indicator.name} turns pink
        </text>
        {[0, 7, 14].map((p) => (
          <text key={p} x={CHART.x - 5} y={yOf(p) + 3} textAnchor="end" className="fill-muted font-mono text-[9px]">
            {p}
          </text>
        ))}
        {[0, 10, 20, 30, 40].filter((v) => v <= vMax).map((v) => (
          <text key={v} x={xOf(v)} y={CHART.y + CHART.h + 13} textAnchor="middle" className="fill-muted font-mono text-[9px]">
            {v}
          </text>
        ))}
        <text x={CHART.x + CHART.w} y={CHART.y + CHART.h + 28} textAnchor="end" className="fill-muted text-[9px]">
          {config.titrant.formula} added / mL
        </text>
        <text x={8} y={CHART.y + 8} className="fill-muted text-[9px]">
          pH
        </text>
        {showCurve && <polyline points={full.join(' ')} className="fill-none stroke-muted" strokeWidth={1.4} />}
        {s.samples.map((p) => (
          <circle key={p.volume} cx={xOf(p.volume)} cy={yOf(p.pH)} r={2.4} className="fill-accent/70" />
        ))}
        <line x1={xOf(s.volume)} x2={xOf(s.volume)} y1={CHART.y} y2={CHART.y + CHART.h} className="stroke-sky-400/60" strokeDasharray="3 3" />
      </svg>
      <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted">
        <input type="checkbox" checked={showCurve} onChange={(e) => setShowCurve(e.target.checked)} />
        Show the full curve (dots are the points you mixed and measured)
      </label>

      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-line text-left text-muted">
            <th className="py-1 font-normal">Trial</th>
            <th className="py-1 font-normal">Titre</th>
            <th className="py-1 font-normal">c({config.titrant.formula})</th>
            <th className="py-1 font-normal"></th>
          </tr>
        </thead>
        <tbody>
          {s.trials.length === 0 && (
            <tr>
              <td colSpan={4} className="py-2 text-muted">
                No endpoint recorded yet.
              </td>
            </tr>
          )}
          {s.trials.map((t, i) => (
            <tr key={i} className="border-b border-line last:border-0">
              <td className="py-1">{t.trial}</td>
              <td className="py-1 font-mono">{t.reading.toFixed(2)} mL</td>
              <td className="py-1 font-mono">{titrantFromReading(config, t.reading).toFixed(4)} M</td>
              <td className="py-1 text-muted">{t.by === 'agent' ? 'tutor demo' : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[11px] text-muted">
        c = {config.analyte.concentration.toFixed(3)} M × {config.analyte.volume.toFixed(2)} mL ÷ titre (1 : 1 reaction)
      </p>
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
