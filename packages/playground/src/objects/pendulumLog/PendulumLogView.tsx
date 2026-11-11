import { cn } from '../../core/cn'
import type { ObjectViewProps } from '../types'
import { connectedTimer, STANDARD_G, type PendulumLogState } from './module'

// Plot ranges: length in m, T² in s².
const X = [0, 1.6]
const Y = [0, 7]
const W = 400
const H = 160
const PAD = { l: 30, r: 8, t: 8, b: 26 }

const px = (l: number) => PAD.l + ((l - X[0]) / (X[1] - X[0])) * (W - PAD.l - PAD.r)
const py = (t2: number) => H - PAD.b - ((t2 - Y[0]) / (Y[1] - Y[0])) * (H - PAD.t - PAD.b)

/** T² against L, with the fitted line and the g it gives. */
export function PendulumLogView({ object, state, dispatch, demonstrating, wiring }: ObjectViewProps<'pendulum-log', PendulumLogState>) {
  const { reading } = connectedTimer(wiring)
  const fit = state.fit
  const at = (l: number) => (fit ? fit.slope * l + fit.intercept : 0)

  return (
    <div className="space-y-3 p-3 text-sm">
      <div className="flex items-center gap-2">
        <p className="min-w-0 flex-1 text-xs text-muted">
          {reading ? (
            <>
              Photogate: <span className="font-mono">{reading.period.toFixed(3)} s</span> at L = <span className="font-mono">{reading.length.toFixed(2)} m</span>
            </>
          ) : (
            'No period yet: clip the photogate onto the pendulum.'
          )}
        </p>
        <button
          type="button"
          data-anchor={`${object.id}/record`}
          disabled={!reading || demonstrating}
          onClick={() => dispatch({ type: 'recordPeriod' })}
          className="shrink-0 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-40"
        >
          Record T
        </button>
        <button
          type="button"
          data-anchor={`${object.id}/fit`}
          disabled={!state.rows.length || demonstrating}
          onClick={() => dispatch({ type: 'fitG' })}
          className="shrink-0 rounded-lg border border-line px-3 py-1.5 text-xs hover:bg-line/50 disabled:opacity-40"
        >
          Fit g
        </button>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" aria-label="Period squared against length">
        <line x1={PAD.l} y1={py(0)} x2={W - PAD.r} y2={py(0)} stroke="currentColor" className="text-line" />
        <line x1={PAD.l} y1={PAD.t} x2={PAD.l} y2={H - PAD.b} stroke="currentColor" className="text-line" />
        {[0, 0.5, 1, 1.5].map((l) => (
          <text key={l} x={px(l)} y={H - PAD.b + 14} textAnchor="middle" className="fill-muted text-[10px]">
            {l}
          </text>
        ))}
        {[0, 2, 4, 6].map((t) => (
          <text key={t} x={PAD.l - 6} y={py(t) + 3} textAnchor="end" className="fill-muted text-[10px]">
            {t}
          </text>
        ))}
        <text x={W - PAD.r} y={H - 2} textAnchor="end" className="fill-muted text-[10px]">
          L (m)
        </text>
        <text x={PAD.l + 4} y={PAD.t + 8} className="fill-muted text-[10px]">
          T² (s²)
        </text>
        {fit && <line x1={px(0)} y1={py(Math.max(Y[0], at(0)))} x2={px(1.6)} y2={py(at(1.6))} stroke="currentColor" strokeWidth="2" strokeDasharray="5 4" className="text-accent" />}
        {state.rows.map((r, i) => (
          <circle key={i} cx={px(r.length)} cy={py(r.period ** 2)} r="5" className={cn(r.amplitude > 15 ? 'fill-warn' : 'fill-accent')} stroke="white" strokeWidth="1.5" />
        ))}
      </svg>

      {fit ? (
        <p className="rounded-lg bg-bg px-3 py-2 font-mono text-xs">
          g = 4π² / slope = {fit.g.toFixed(2)} m/s² <span className="text-muted">({((Math.abs(fit.g - STANDARD_G) / STANDARD_G) * 100).toFixed(1)}% from 9.81)</span>
        </p>
      ) : (
        state.rows.length > 0 && <p className="text-xs text-muted">Orange points were released above 15°.</p>
      )}

      <table className="w-full text-xs">
        <thead className="text-left text-muted">
          <tr className="border-b border-line">
            <th className="py-1 font-normal">L (m)</th>
            <th className="py-1 font-normal">Mass</th>
            <th className="py-1 font-normal">Release</th>
            <th className="py-1 text-right font-normal">T (s)</th>
            <th className="py-1 text-right font-normal">T² (s²)</th>
          </tr>
        </thead>
        <tbody>
          {state.rows.map((r, i) => (
            <tr key={i} className="border-b border-line/60">
              <td className="py-1 font-mono">{r.length.toFixed(2)}</td>
              <td className="py-1 font-mono">{r.mass} g</td>
              <td className={cn('py-1 font-mono', r.amplitude > 15 && 'text-warn')}>{r.amplitude}°</td>
              <td className="py-1 text-right font-mono">{r.period.toFixed(3)}</td>
              <td className="py-1 text-right font-mono">
                {(r.period ** 2).toFixed(3)}
                {r.by === 'agent' && <span className="ml-1 text-[10px] text-accent">tutor</span>}
              </td>
            </tr>
          ))}
          {!state.rows.length && (
            <tr>
              <td colSpan={5} className="py-2 text-center text-muted">
                No periods yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
