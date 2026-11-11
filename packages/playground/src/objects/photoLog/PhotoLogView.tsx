import { PLANCK, lineColour } from '../photoelectric/physics'
import type { ObjectViewProps } from '../types'
import { connectedRig, planckOf, type PhotoLogState } from './module'

// Plot ranges: frequency in 10¹⁴ Hz, V₀ in volts.
const X = [4, 9]
const Y = [0, 1.4]
const W = 400
const H = 170
const PAD = { l: 34, r: 8, t: 8, b: 26 }

const px = (f: number) => PAD.l + ((f - X[0]) / (X[1] - X[0])) * (W - PAD.l - PAD.r)
const py = (v: number) => H - PAD.b - ((v - Y[0]) / (Y[1] - Y[0])) * (H - PAD.t - PAD.b)

/** V₀ against frequency, with the fitted line and what it gives for h and φ. */
export function PhotoLogView({ object, state, dispatch, demonstrating, wiring }: ObjectViewProps<'photo-log', PhotoLogState>) {
  const rig = connectedRig(wiring)
  const fit = state.fit
  const h = fit ? planckOf(fit) : null
  // The fitted line from the x-axis crossing (threshold) to where it leaves the plot.
  const line = fit && (() => {
    const at = (f14: number) => fit.slope * f14 * 1e14 + fit.intercept
    const fAt = (v: number) => (v - fit.intercept) / fit.slope / 1e14
    const f0 = fAt(0)
    const from = Math.max(X[0], f0)
    const to = fit.slope > 0 ? Math.min(X[1], fAt(Y[1])) : X[1]
    return { x1: px(from), y1: py(at(from)), x2: px(to), y2: py(at(to)), f0 }
  })()

  return (
    <div className="space-y-3 p-3 text-sm">
      <div className="flex items-center gap-2">
        <p className="min-w-0 flex-1 text-xs text-muted">
          {rig ? (
            <>
              {rig.line} at <span className="font-mono">{rig.voltage.toFixed(2)} V</span>, meter{' '}
              <span className="font-mono">{rig.current.toFixed(1)} nA</span>
            </>
          ) : (
            "No rig connected. Plug the rig's data cable into the socket on the left."
          )}
        </p>
        <button
          type="button"
          data-anchor={`${object.id}/record`}
          disabled={!rig || demonstrating}
          onClick={() => dispatch({ type: 'recordStop' })}
          className="shrink-0 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-40"
        >
          Record V₀
        </button>
        <button
          type="button"
          data-anchor={`${object.id}/fit`}
          disabled={!state.rows.length || demonstrating}
          onClick={() => dispatch({ type: 'fitLine' })}
          className="shrink-0 rounded-lg border border-line px-3 py-1.5 text-xs hover:bg-line/50 disabled:opacity-40"
        >
          Fit line
        </button>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" aria-label="Stopping voltage against frequency">
        <line x1={PAD.l} y1={py(0)} x2={W - PAD.r} y2={py(0)} stroke="currentColor" className="text-line" />
        <line x1={PAD.l} y1={PAD.t} x2={PAD.l} y2={H - PAD.b} stroke="currentColor" className="text-line" />
        {[4, 5, 6, 7, 8, 9].map((f) => (
          <text key={f} x={px(f)} y={H - PAD.b + 14} textAnchor="middle" className="fill-muted text-[10px]">
            {f}
          </text>
        ))}
        {[0, 0.5, 1].map((v) => (
          <text key={v} x={PAD.l - 6} y={py(v) + 3} textAnchor="end" className="fill-muted text-[10px]">
            {v.toFixed(1)}
          </text>
        ))}
        <text x={W - PAD.r} y={H - 2} textAnchor="end" className="fill-muted text-[10px]">
          f (10¹⁴ Hz)
        </text>
        <text x={PAD.l + 4} y={PAD.t + 8} className="fill-muted text-[10px]">
          V₀ (V)
        </text>
        {line && <line {...line} stroke="currentColor" strokeWidth="2" strokeDasharray="5 4" className="text-accent" />}
        {line && line.f0 > X[0] && <circle cx={px(line.f0)} cy={py(0)} r="3.5" className="fill-accent" />}
        {state.rows.map((r, i) => (
          <circle key={i} cx={px(r.frequency / 1e14)} cy={py(r.v0)} r="5" fill={lineColour(r.wavelength)} stroke="white" strokeWidth="1.5" />
        ))}
      </svg>

      {fit && h !== null && line ? (
        <p className="rounded-lg bg-bg px-3 py-2 font-mono text-xs leading-5">
          h = e × slope = {(h / 1e-34).toFixed(2)} × 10⁻³⁴ J·s{' '}
          <span className="text-muted">({((Math.abs(h - PLANCK) / PLANCK) * 100).toFixed(1)}% from 6.63)</span>
          <br />φ = {(-fit.intercept).toFixed(2)} eV · f₀ = {line.f0.toFixed(2)} × 10¹⁴ Hz
        </p>
      ) : (
        state.rows.length > 0 && <p className="text-xs text-muted">Fit a line once you have V₀ for every line that gives a current.</p>
      )}

      <table className="w-full text-xs">
        <thead className="text-left text-muted">
          <tr className="border-b border-line">
            <th className="py-1 font-normal">Line</th>
            <th className="py-1 font-normal">f (10¹⁴ Hz)</th>
            <th className="py-1 font-normal">Intensity</th>
            <th className="py-1 text-right font-normal">V₀ (V)</th>
          </tr>
        </thead>
        <tbody>
          {state.rows.map((r, i) => (
            <tr key={i} className="border-b border-line/60">
              <td className="py-1">
                {r.line} <span className="text-muted">{r.wavelength} nm</span>
              </td>
              <td className="py-1 font-mono">{(r.frequency / 1e14).toFixed(3)}</td>
              <td className="py-1 font-mono">{r.intensity * 100}%</td>
              <td className="py-1 text-right font-mono">
                {r.v0.toFixed(2)}
                {r.by === 'agent' && <span className="ml-1 text-[10px] text-accent">tutor</span>}
              </td>
            </tr>
          ))}
          {!state.rows.length && (
            <tr>
              <td colSpan={4} className="py-2 text-center text-muted">
                No stopping voltages yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
