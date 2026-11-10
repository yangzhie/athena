import { useBodyDrag } from '../../core/useBodyDrag'
import type { ObjectViewProps } from '../types'
import { formatConc } from './electrochem'
import type { HalfCellState } from './module'
import { HALF_CELL } from './module'

const METAL: Record<string, string> = { Zn: '#a1a1aa', Cu: '#c2410c', Ag: '#d4d4d8', Fe: '#71717a', Pb: '#64748b', Mg: '#e4e4e7' }

/** A beaker with a metal electrode, drawn straight onto the canvas. Drag the glass to move it. */
export function HalfCellView({ object, state, dispatch, demonstrating, moveTo }: ObjectViewProps<'half-cell', HalfCellState>) {
  const { metal, ion, concentration: start, solutionColor } = object.config
  const drag = useBodyDrag(object.rect, moveTo, demonstrating)
  const id = object.id
  // Diluting fades the colour of a coloured solution.
  const strength = Math.max(0.15, Math.min(1, 1 + Math.log10(state.concentration) / 3))
  const glass = 'M28,92 L28,232 Q28,246 42,246 L158,246 Q172,246 172,232 L172,92'

  return (
    <svg width={HALF_CELL.w} height={HALF_CELL.h} className="overflow-visible">
      <g className={demonstrating ? 'pointer-events-auto' : 'pointer-events-auto cursor-grab active:cursor-grabbing'} data-anchor={`${id}/beaker`} {...drag}>
        <path d={`${glass} Z`} fill="transparent" />
        {/* Solution */}
        <path d="M30,128 L170,128 L170,232 Q170,244 158,244 L42,244 Q30,244 30,232 Z" fill={solutionColor} fillOpacity={0.55 * strength} />
        <line x1={30} y1={128} x2={170} y2={128} stroke={solutionColor} strokeOpacity={0.9 * strength} strokeWidth={2} />
        {/* Electrode */}
        <rect x={52} y={36} width={20} height={196} rx={2} fill={METAL[metal] ?? '#a1a1aa'} stroke="#52525b" strokeWidth={1} />
        <text x={62} y={186} textAnchor="middle" transform="rotate(-90 62 186)" className="pointer-events-none fill-white text-[11px] font-semibold">
          {metal}
        </text>
        {/* Glass */}
        <path d={glass} fill="none" className="stroke-ink/60" strokeWidth={2.5} />
        <path d="M20,92 L36,92 M164,92 L180,92" className="stroke-ink/60" strokeWidth={2.5} />
      </g>
      {/* Terminal clip where a lead attaches */}
      <g data-anchor={`${id}/electrode`}>
        <rect x={54} y={22} width={16} height={14} rx={3} className="fill-surface stroke-ink/60" strokeWidth={1.5} />
      </g>
      <text x={100} y={268} textAnchor="middle" className="pointer-events-none fill-ink text-[14px] font-semibold">
        {metal} | {ion}(aq)
      </text>
      <text x={100} y={285} textAnchor="middle" className="pointer-events-none fill-muted font-mono text-[11px]">
        {formatConc(state.concentration)}
      </text>
      <foreignObject x={10} y={290} width={180} height={24}>
        <div className="flex h-full items-center justify-center gap-1.5">
          <button
            type="button"
            data-anchor={`${id}/dilute`}
            disabled={demonstrating}
            onClick={() => dispatch({ type: 'dilute' })}
            className="pointer-events-auto rounded border border-line bg-surface px-2 py-0.5 text-[11px] hover:bg-bg disabled:opacity-50"
          >
            Dilute ×10
          </button>
          {state.concentration !== start && (
            <button
              type="button"
              data-anchor={`${id}/refill`}
              disabled={demonstrating}
              onClick={() => dispatch({ type: 'refill' })}
              className="pointer-events-auto rounded border border-line bg-surface px-2 py-0.5 text-[11px] hover:bg-bg disabled:opacity-50"
            >
              Refill {formatConc(start)}
            </button>
          )}
        </div>
      </foreignObject>
    </svg>
  )
}
