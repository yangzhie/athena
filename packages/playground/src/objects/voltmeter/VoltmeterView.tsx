import { useBodyDrag } from '../../core/useBodyDrag'
import { formatVolts, measure } from '../halfCell/electrochem'
import type { ObjectViewProps } from '../types'
import { VOLTMETER } from './module'

/**
 * A digital voltmeter. It shows only what a real meter would: the potential
 * of the red (V) lead relative to the black (COM) lead, 0 when no current path.
 */
export function VoltmeterView({ object, wiring, demonstrating, moveTo }: ObjectViewProps<'voltmeter', null>) {
  const drag = useBodyDrag(object.rect, moveTo, demonstrating)
  const m = measure(wiring)
  return (
    <svg width={VOLTMETER.w} height={VOLTMETER.h} className="overflow-visible">
      <g className={demonstrating ? 'pointer-events-auto' : 'pointer-events-auto cursor-grab active:cursor-grabbing'} data-anchor={`${object.id}/body`} {...drag}>
        <rect x={2} y={2} width={226} height={146} rx={16} fill="#facc15" stroke="#a16207" strokeWidth={2} />
        <rect x={18} y={16} width={194} height={70} rx={8} fill="#1c1917" />
        <rect x={26} y={24} width={178} height={54} rx={4} fill="#bef264" />
        <text x={192} y={64} textAnchor="end" className="pointer-events-none fill-stone-900 font-mono text-[32px] font-semibold">
          {formatVolts(m.volts)}
        </text>
        <text x={34} y={40} className="pointer-events-none fill-stone-700 font-mono text-[10px]">
          DC V
        </text>
        <text x={115} y={108} textAnchor="middle" className="pointer-events-none fill-stone-800 text-[10px] font-semibold">
          Simulated · Nernst, 25 °C
        </text>
      </g>
      {/* Terminals */}
      {(
        [
          [80, 'COM', '#3f3f46'],
          [150, 'V', '#e11d48'],
        ] as const
      ).map(([x, label, color]) => (
        <g key={label} className="pointer-events-none">
          <circle cx={x} cy={128} r={9} fill={color} stroke="#1c1917" strokeWidth={1.5} />
          <text x={x + 14} y={132} className="fill-stone-800 text-[10px] font-semibold">
            {label}
          </text>
        </g>
      ))}
    </svg>
  )
}
