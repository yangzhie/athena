import type { Action, Check, Condition, Observation } from '../contracts'

export function evaluate(condition: Condition, obs: Observation): boolean {
  if ('all' in condition) return condition.all.every((c) => evaluate(c, obs))
  if ('any' in condition) return condition.any.some((c) => evaluate(c, obs))
  const actual = obs[condition.field]
  if (actual === undefined) return false
  switch (condition.op) {
    case 'eq':
      return actual === condition.value
    case 'ne':
      return actual !== condition.value
    case 'oneOf':
      return condition.value.includes(actual)
    case 'between':
      return typeof actual === 'number' && actual >= condition.value[0] && actual <= condition.value[1]
    case 'lt':
      return typeof actual === 'number' && actual < condition.value
    case 'lte':
      return typeof actual === 'number' && actual <= condition.value
    case 'gt':
      return typeof actual === 'number' && actual > condition.value
    case 'gte':
      return typeof actual === 'number' && actual >= condition.value
  }
}

/** The first check (in scene order) that applies to this action, if any. */
export function matchCheck(checks: Check[], action: Action, obs: Observation): Check | null {
  return checks.find((c) => c.objectId === action.objectId && c.on.includes(action.type) && evaluate(c.when, obs)) ?? null
}
