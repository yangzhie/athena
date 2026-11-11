import { demoScenes } from '@athena/playground/fixtures'

export interface PreparedScene {
  id: string
  /** e.g. "Bubble sort" (the scene title without its "Algorithms ·" prefix). */
  title: string
  goal: string
}

/**
 * The hand-built Playground scenes each demo unit offers (docs/demo-units.md).
 * Hard-coded for the demo: other units still get model-generated scenes.
 */
const BY_UNIT: Record<string, string[]> = {
  CHEM1001: ['galvanic-cells', 'naoh-standardisation', 'argon-balance'],
  PHYS1001: ['pendulum-g', 'photoelectric-planck'],
  COMP1001: ['bubble-sort', 'cleaning-average'],
}

const byId = new Map(demoScenes.map((d) => [d.scene.id, d]))

export const isPrepared = (sceneId: string) => byId.has(sceneId)

function toPrepared(id: string): PreparedScene | null {
  const d = byId.get(id)
  if (!d) return null
  return { id, title: d.scene.title.split('·').pop()!.trim(), goal: d.scene.goal }
}

/** A unit's prepared scenes, the one that best fits the lesson goal first. */
export function preparedFor(unitCode: string, goal = ''): PreparedScene[] {
  const ids = BY_UNIT[unitCode] ?? []
  const fits = (id: string) => (goal && byId.get(id)?.match.test(goal) ? 0 : 1)
  return [...ids].sort((a, b) => fits(a) - fits(b)).map(toPrepared).filter((s): s is PreparedScene => s !== null)
}
