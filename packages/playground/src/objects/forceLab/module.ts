import type { ForceLabConfig, Rect } from '../../contracts'
import { defineModule } from '../types'
import { forceAt, regimeAt } from './curve'
import { ForceLabView } from './ForceLabView'
import { s } from '../../core/schema'

/** World pixels per nanometre. Atoms live directly on the canvas at this scale. */
export const PX_PER_NM = 400
/** Room around the atoms for force arrows and labels. */
export const MARGIN = 110

export interface Point {
  x: number
  y: number
}

export interface ForceLabState {
  /** World coordinates of the two particle centres. */
  particles: [Point, Point]
  range: [number, number]
  radii: [number, number]
  /** Distances visited so far (nm), for the readout's trail. */
  trail: number[]
}

export function distanceOf(s: ForceLabState) {
  const [a, b] = s.particles
  return Math.hypot(b.x - a.x, b.y - a.y) / PX_PER_NM
}

/** Keep the distance inside the scene's range by sliding `moving` along the line from `fixed`. */
function constrain(fixed: Point, moving: Point, range: [number, number]): Point {
  let dx = moving.x - fixed.x
  let dy = moving.y - fixed.y
  let len = Math.hypot(dx, dy)
  if (len < 1e-6) {
    dx = 1
    dy = 0
    len = 1
  }
  const r = Math.min(range[1], Math.max(range[0], len / PX_PER_NM)) * PX_PER_NM
  return { x: fixed.x + (dx / len) * r, y: fixed.y + (dy / len) * r }
}

function withTrail(s: ForceLabState): ForceLabState {
  const d = distanceOf(s)
  if (s.trail.some((t) => Math.abs(t - d) < 0.004)) return s
  return { ...s, trail: [...s.trail.slice(-300), d] }
}

const round = (x: number, digits = 3) => Number(x.toFixed(digits))

export const forceLabModule = defineModule<'force-lab', ForceLabState>({
  type: 'force-lab',
  label: 'Force lab',
  about: {
    summary:
      'Two particles drawn on the canvas; the student drags either one and sees the net force along the line between them. The force comes from key points you give (interpolated locally), so label it ai-estimate.',
    config: s.object({
      particles: s.array(
        s.object({ label: s.string('Short label, e.g. "Ar"'), color: s.string('CSS colour'), radius: s.number('Drawing radius in nm', 0.03, 0.3) }),
        'Exactly two particles',
        2,
        2,
      ),
      curve: s.array(s.object({ r: s.number('Distance in nm'), f: s.number('Net force; positive = repulsion') }), 'Key points, sorted by r', 4, 40),
      forceUnit: s.string(),
      range: s.array(s.number(), '[min, max] distance in nm the student can reach', 2, 2),
      initialDistance: s.number('nm'),
    }),
    actions: { setDistance: '{distance}: move the second particle to this distance (nm)', moveParticle: '{index, x, y}: world coordinates' },
    observes: {
      on: ['moveParticle', 'setDistance'],
      fields: { distance: 'nm', force: 'net force in forceUnit', regime: '"repulsive", "balanced", "attractive" or "negligible"' },
    },
  },
  width: 620,
  init: (config: ForceLabConfig) => ({
    particles: [
      { x: 0, y: 0 },
      { x: config.initialDistance * PX_PER_NM, y: 0 },
    ],
    range: config.range,
    radii: [config.particles[0].radius * PX_PER_NM, config.particles[1].radius * PX_PER_NM],
    trail: [config.initialDistance],
  }),
  bounds(state) {
    const xs = state.particles.map((p) => p.x)
    const ys = state.particles.map((p) => p.y)
    const pad = Math.max(...state.radii) + MARGIN
    const x = Math.min(...xs) - pad
    const y = Math.min(...ys) - pad
    return { x, y, w: Math.max(...xs) + pad - x, h: Math.max(...ys) + pad - y } satisfies Rect
  },
  placeAt(state, x, y) {
    const pad = Math.max(...state.radii) + MARGIN
    const dx = x + pad - Math.min(...state.particles.map((p) => p.x))
    const dy = y + pad - Math.min(...state.particles.map((p) => p.y))
    return { ...state, particles: state.particles.map((p) => ({ x: p.x + dx, y: p.y + dy })) as [Point, Point] }
  },
  edits: ['moveParticle', 'setDistance'],
  reduce(state, action) {
    if (action.type === 'moveParticle') {
      const other = state.particles[1 - action.index]
      const moved = constrain(other, { x: action.x, y: action.y }, state.range)
      const particles: [Point, Point] = action.index === 0 ? [moved, other] : [other, moved]
      return withTrail({ ...state, particles })
    }
    if (action.type === 'setDistance') {
      const [a, b] = state.particles
      const len = Math.hypot(b.x - a.x, b.y - a.y) || 1
      const target = { x: a.x + ((b.x - a.x) / len) * action.distance * PX_PER_NM, y: a.y + ((b.y - a.y) / len) * action.distance * PX_PER_NM }
      return withTrail({ ...state, particles: [a, constrain(a, target, state.range)] })
    }
    return state
  },
  observe(state, action, config) {
    if (action.type !== 'moveParticle' && action.type !== 'setDistance') return null
    const d = distanceOf(state)
    return {
      action: action.type,
      distance: round(d),
      force: round(forceAt(config.curve, d), 2),
      regime: regimeAt(config.curve, d),
    }
  },
  tween(state, action) {
    if (action.type !== 'setDistance') return []
    const from = distanceOf(state)
    const frames = 45
    return Array.from({ length: frames }, (_, i) => {
      const t = (i + 1) / frames
      const k = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2
      return { type: 'setDistance' as const, distance: from + (action.distance - from) * k }
    })
  },
  anchor: (action) => (action.type === 'moveParticle' ? `particle-${action.index}` : 'particle-1'),
  summarize(state, config) {
    const d = distanceOf(state)
    return {
      distance_nm: round(d),
      force: round(forceAt(config.curve, d), 2),
      forceUnit: config.forceUnit,
      regime: regimeAt(config.curve, d),
      particles: config.particles.map((p) => p.label),
    }
  },
  View: ForceLabView,
})
