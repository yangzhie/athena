import { useRef, type PointerEvent } from 'react'
import { cn } from '../../core/cn'
import type { ObjectViewProps } from '../types'
import { distanceFor, intensityAt, LAMP_RANGE, MAX_VOLTAGE, readingOf, type PhotoelectricState } from './module'
import { lineColour } from './physics'

const W = 440
const H = 250
/** The spectrum strip: wavelength range and where it sits. */
const SPECTRUM = { x0: 70, x1: 420, y: 30, nm: [340, 600] as const }
const nmX = (nm: number) => SPECTRUM.x0 + ((nm - SPECTRUM.nm[0]) / (SPECTRUM.nm[1] - SPECTRUM.nm[0])) * (SPECTRUM.x1 - SPECTRUM.x0)
/** The lamp rail: x of the lamp's centre at 10 cm and at 20 cm from the tube. */
const RAIL = { near: 140, far: 40, y: 125 }
const cmX = (cm: number, [near, far]: readonly [number, number]) => RAIL.near + ((cm - near) / (far - near)) * (RAIL.far - RAIL.near)
/** The voltage knob: centre, radius, and the sweep from 0 V to the maximum. */
const KNOB = { x: 392, y: 212, r: 22, sweep: 270 }
const TUBE = { x: 290, y: 125 }

type Gesture = 'line' | 'lamp' | 'knob'

/**
 * Lamp, phototube, retarding supply and nanoammeter on one bench, worked by
 * hand: slide the selector along the spectrum to pick a line, slide the lamp
 * along its rail (closer is brighter), and turn the knob for the voltage.
 */
export function PhotoelectricView({ object, state, dispatch, preview, demonstrating, highlight }: ObjectViewProps<'photoelectric', PhotoelectricState>) {
  const svg = useRef<SVGSVGElement>(null)
  const gesture = useRef<Gesture | null>(null)
  const { config } = object
  const r = readingOf(state, config)
  const colour = lineColour(r.wavelength)
  const lampX = cmX(distanceFor(state.intensity), LAMP_RANGE)
  const electrons = Math.min(8, Math.ceil(r.current / 5))
  const knobAngle = (state.voltage / MAX_VOLTAGE) * KNOB.sweep - KNOB.sweep / 2
  const ring = (part: string) => highlight?.part === part && 'stroke-warn'
  const id = object.id

  const local = (e: PointerEvent<Element>) => {
    const box = svg.current!.getBoundingClientRect()
    const k = W / box.width
    return { x: (e.clientX - box.left) * k, y: (e.clientY - box.top) * k }
  }
  const nearestLine = (x: number) =>
    config.lines.reduce((best, l, i) => (Math.abs(nmX(l.wavelength) - x) < Math.abs(nmX(config.lines[best].wavelength) - x) ? i : best), 0)
  const actionAt = (g: Gesture, p: { x: number; y: number }) => {
    if (g === 'line') return { type: 'selectLine' as const, index: nearestLine(p.x) }
    if (g === 'lamp') {
      const cm = LAMP_RANGE[0] + ((p.x - RAIL.near) / (RAIL.far - RAIL.near)) * (LAMP_RANGE[1] - LAMP_RANGE[0])
      return { type: 'setIntensity' as const, level: intensityAt(Math.min(LAMP_RANGE[1], Math.max(LAMP_RANGE[0], cm))) }
    }
    // Knob: 0 V at the lower left, the maximum at the lower right, clockwise.
    const deg = (Math.atan2(p.x - KNOB.x, KNOB.y - p.y) * 180) / Math.PI
    const clamped = Math.min(KNOB.sweep / 2, Math.max(-KNOB.sweep / 2, deg))
    return { type: 'setVoltage' as const, volts: ((clamped + KNOB.sweep / 2) / KNOB.sweep) * MAX_VOLTAGE }
  }
  const begin = (e: PointerEvent<SVGGElement>) => {
    if (demonstrating) return
    e.stopPropagation()
    e.currentTarget.setPointerCapture(e.pointerId)
    gesture.current = e.currentTarget.dataset.gesture as Gesture
    // A tap on a line in the spectrum picks it straight away.
    if (gesture.current === 'line') preview(actionAt('line', local(e)))
  }
  const move = (e: PointerEvent<SVGGElement>) => {
    if (gesture.current) preview(actionAt(gesture.current, local(e)))
  }
  const end = (e: PointerEvent<SVGGElement>) => {
    const g = gesture.current
    gesture.current = null
    if (g) dispatch(actionAt(g, local(e)))
  }
  const handle = { onPointerDown: begin, onPointerMove: move, onPointerUp: end, onPointerCancel: end, className: 'pointer-events-auto' }

  return (
    <svg ref={svg} viewBox={`0 0 ${W} ${H}`} className="w-full select-none" aria-label={`${r.line} light on the ${config.cathode.label} cathode`}>
      {/* Spectrum: slide the selector, or tap a line */}
      <text x={8} y={SPECTRUM.y - 2} className="fill-muted text-[10px]">
        Lamp line
      </text>
      <text x={8} y={SPECTRUM.y + 12} className="fill-ink text-[11px] font-semibold">
        {r.line}
      </text>
      <g {...handle} data-gesture="line" style={{ cursor: demonstrating ? 'default' : 'ew-resize' }}>
        <rect x={SPECTRUM.x0 - 10} y={SPECTRUM.y - 16} width={SPECTRUM.x1 - SPECTRUM.x0 + 20} height={44} fill="transparent" />
        <line x1={SPECTRUM.x0} y1={SPECTRUM.y} x2={SPECTRUM.x1} y2={SPECTRUM.y} className="stroke-line" strokeWidth={6} strokeLinecap="round" />
        {config.lines.map((l, i) => (
          <g key={i} data-anchor={`${id}/line-${i}`}>
            <line x1={nmX(l.wavelength)} y1={SPECTRUM.y - 8} x2={nmX(l.wavelength)} y2={SPECTRUM.y + 8} stroke={lineColour(l.wavelength)} strokeWidth={4} />
            <text x={nmX(l.wavelength)} y={SPECTRUM.y + 22} textAnchor="middle" className={cn('text-[9px]', i === state.line ? 'fill-ink font-semibold' : 'fill-muted')}>
              {Math.round(l.wavelength)}
            </text>
          </g>
        ))}
        <path d={`M${nmX(r.wavelength) - 7},${SPECTRUM.y - 18} l14,0 l-7,9 z`} className="fill-accent" />
      </g>

      {/* Lamp on its rail: slide it closer (brighter) or further (dimmer) */}
      <line x1={RAIL.far - 24} y1={RAIL.y + 26} x2={RAIL.near + 24} y2={RAIL.y + 26} className="stroke-line" strokeWidth={3} />
      <polygon points={`${lampX + 18},${RAIL.y - 10} ${TUBE.x - 82},${RAIL.y - 22} ${TUBE.x - 82},${RAIL.y + 22} ${lampX + 18},${RAIL.y + 10}`} fill={colour} opacity={0.1 + 0.35 * state.intensity} className="pointer-events-none" />
      <g {...handle} data-gesture="lamp" data-anchor={`${id}/lamp`} style={{ cursor: demonstrating ? 'default' : 'ew-resize' }}>
        <rect x={lampX - 18} y={RAIL.y - 18} width={36} height={36} rx={8} className={cn('fill-bg stroke-muted', ring('lamp'))} strokeWidth={2} />
        <circle cx={lampX} cy={RAIL.y} r={7} fill={colour} />
        <line x1={lampX} y1={RAIL.y + 18} x2={lampX} y2={RAIL.y + 26} className="stroke-muted" strokeWidth={2} />
      </g>
      <text x={(RAIL.far + RAIL.near) / 2} y={RAIL.y + 42} textAnchor="middle" className="pointer-events-none fill-muted font-mono text-[10px]">
        {distanceFor(state.intensity).toFixed(1)} cm · {Math.round(state.intensity * 100)}%
      </text>

      {/* Phototube */}
      <ellipse cx={TUBE.x} cy={TUBE.y} rx={90} ry={46} className="fill-surface stroke-line" strokeWidth={2} />
      <path d={`M${TUBE.x - 72},${TUBE.y - 30} Q${TUBE.x - 90},${TUBE.y} ${TUBE.x - 72},${TUBE.y + 30}`} fill="none" stroke="currentColor" strokeWidth={5} className="text-muted" />
      <line x1={TUBE.x + 70} y1={TUBE.y - 26} x2={TUBE.x + 70} y2={TUBE.y + 26} stroke="currentColor" strokeWidth={4} className="text-muted" />
      {Array.from({ length: electrons }, (_, i) => (
        <circle key={i} cx={TUBE.x - 55 + ((i * 37) % 120)} cy={TUBE.y - 20 + ((i * 23) % 40)} r={4} className="fill-accent" />
      ))}
      {!electrons && r.v0 <= 0 && (
        <text x={TUBE.x} y={TUBE.y + 4} textAnchor="middle" className="fill-muted text-[11px]">
          no electrons emitted
        </text>
      )}
      <text x={TUBE.x - 72} y={TUBE.y + 62} textAnchor="middle" className="fill-muted text-[10px]">
        {config.cathode.label} cathode
      </text>
      <text x={SPECTRUM.x1} y={SPECTRUM.y + 36} textAnchor="end" className="fill-muted text-[9px]">
        wavelength, nm
      </text>

      {/* Nanoammeter */}
      <rect x={14} y={186} width={190} height={50} rx={8} className="fill-bg" />
      <text x={24} y={206} className="fill-muted text-[10px]">
        Photocurrent
      </text>
      <text x={194} y={226} textAnchor="end" className={cn('font-mono text-[22px] font-semibold', r.current === 0 ? 'fill-muted' : 'fill-ink')}>
        {r.current.toFixed(1)} nA
      </text>

      {/* Retarding voltage knob: turn it */}
      <text x={KNOB.x - KNOB.r - 10} y={KNOB.y - 4} textAnchor="end" className="fill-muted text-[10px]">
        Retarding voltage
      </text>
      <text x={KNOB.x - KNOB.r - 10} y={KNOB.y + 14} textAnchor="end" className="fill-ink font-mono text-[14px] font-semibold">
        {state.voltage.toFixed(2)} V
      </text>
      <g {...handle} data-gesture="knob" data-anchor={`${id}/knob`} style={{ cursor: demonstrating ? 'default' : 'grab' }}>
        <circle cx={KNOB.x} cy={KNOB.y} r={KNOB.r + 8} fill="transparent" />
        <circle cx={KNOB.x} cy={KNOB.y} r={KNOB.r} className={cn('fill-surface stroke-muted', ring('knob'))} strokeWidth={2} />
        <line
          x1={KNOB.x}
          y1={KNOB.y}
          x2={KNOB.x + Math.sin((knobAngle * Math.PI) / 180) * (KNOB.r - 4)}
          y2={KNOB.y - Math.cos((knobAngle * Math.PI) / 180) * (KNOB.r - 4)}
          className="stroke-accent"
          strokeWidth={3}
          strokeLinecap="round"
        />
      </g>
    </svg>
  )
}
