import { formatVolts } from '../halfCell/electrochem'
import type { ObjectViewProps } from '../types'
import { connectedReading, type PotentialLogState } from './module'

/** A notebook page: records whatever the instrument plugged into it shows. */
export function PotentialLogView({ object, state, dispatch, demonstrating, wiring }: ObjectViewProps<'potential-log', PotentialLogState>) {
  const m = connectedReading(wiring)
  return (
    <div className="space-y-3 p-3 text-sm">
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          {m ? (
            <p>
              Meter shows <span className="font-mono font-semibold">{formatVolts(m.volts)} V</span>
            </p>
          ) : (
            <p className="text-muted">No instrument connected. Plug a meter's data cable into the socket on the left.</p>
          )}
        </div>
        <button
          type="button"
          data-anchor={`${object.id}/record`}
          disabled={!m || demonstrating}
          onClick={() => dispatch({ type: 'recordReading' })}
          className="shrink-0 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-40"
        >
          Record reading
        </button>
      </div>

      <table className="w-full text-xs">
        <thead className="text-left text-muted">
          <tr className="border-b border-line">
            <th className="py-1 font-normal">#</th>
            <th className="py-1 font-normal">Red lead (V)</th>
            <th className="py-1 font-normal">Black lead (COM)</th>
            <th className="py-1 text-right font-normal">E (V)</th>
          </tr>
        </thead>
        <tbody>
          {state.rows.map((r) => (
            <tr key={r.n} className="border-b border-line/60">
              <td className="py-1 text-muted">{r.n}</td>
              <td className="py-1">{r.red ?? '—'}</td>
              <td className="py-1">{r.black ?? '—'}</td>
              <td className="py-1 text-right font-mono">
                {formatVolts(r.volts)}
                {r.by === 'agent' && <span className="ml-1 text-[10px] text-accent">tutor</span>}
              </td>
            </tr>
          ))}
          {!state.rows.length && (
            <tr>
              <td colSpan={4} className="py-2 text-center text-muted">
                No readings yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
