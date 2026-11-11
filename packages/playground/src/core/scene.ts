import type { Condition, DemoAction, ObjectSpec, Scene, ToolCall, TutorResponse } from '../contracts'
import type { AnyModule } from '../objects/types'
import { validate } from './schema'

const PROVENANCE = ['real-run', 'simulated', 'ai-estimate', 'concept', 'material']
const RELATIONS = ['from', 'contrast', 'explains']
const VERDICTS = ['correct', 'hint', 'misconception']
const WIRING_ACTIONS = ['connect', 'swapPlugs']

/**
 * The component catalog: everything the model needs to compose a scene from
 * the preset object types. Generated from the modules, so it never drifts.
 */
export function componentCatalog(modules: AnyModule[]) {
  return modules.map((m) => ({
    type: m.type,
    label: m.label,
    summary: m.about.summary,
    drawnAs: m.bounds || m.size ? 'apparatus drawn on the canvas' : 'card',
    config: m.about.config,
    ...(m.ports && {
      ports: Object.fromEntries(
        Object.entries(m.ports).map(([id, p]) => [id, { kind: p.kind, role: p.role, ...(p.about ? { about: p.about } : {}) }]),
      ),
    }),
    ...(m.about.actions && { actions: m.about.actions }),
    ...(m.about.observes && { checkable: m.about.observes }),
  }))
}

function fieldsOf(c: Condition): string[] {
  if ('all' in c) return c.all.flatMap(fieldsOf)
  if ('any' in c) return c.any.flatMap(fieldsOf)
  return [c.field]
}

const fieldAllowed = (field: string, declared: Record<string, string>) =>
  field === 'action' || field in declared || Object.keys(declared).some((d) => d.endsWith('.*') && field.startsWith(d.slice(0, -1)))

/**
 * Check a scene before it opens. Every message names the path of the problem,
 * so a model can repair its own output; an empty list means the scene is valid.
 */
export function validateScene(scene: Scene, moduleList: AnyModule[]): string[] {
  const modules = Object.fromEntries(moduleList.map((m) => [m.type, m]))
  const errors: string[] = []
  const checks = scene.checks ?? []
  const types = new Map<string, string>() // object id → type, including objects the tutor adds later

  for (const key of ['id', 'title', 'goal'] as const) if (!scene[key]?.trim()) errors.push(`scene.${key} is required`)
  if (!scene.objects?.length) errors.push('scene.objects must not be empty')

  const checkObject = (spec: ObjectSpec, path: string, earlier: Set<string>) => {
    const mod = modules[spec.type]
    if (!spec.id) errors.push(`${path}.id is required`)
    else if (types.has(spec.id)) errors.push(`${path}.id '${spec.id}' is used twice`)
    if (!mod) {
      errors.push(`${path}.type '${spec.type}' is not a known type (${moduleList.map((m) => m.type).join(', ')})`)
      return
    }
    types.set(spec.id, spec.type)
    errors.push(...validate(mod.about.config, spec.config, `${path}.config`))
    if (!PROVENANCE.includes(spec.provenance)) errors.push(`${path}.provenance must be one of ${PROVENANCE.join(', ')}`)
    if (spec.near && !earlier.has(spec.near)) errors.push(`${path}.near '${spec.near}' must be an object placed before it`)
    earlier.add(spec.id)
  }
  const placed = new Set<string>()
  scene.objects?.forEach((o, i) => checkObject(o, `objects[${i}]`, placed))

  // Objects the tutor may add in its responses can be referenced by the other responses.
  const responses: [string, TutorResponse][] = []
  const collect = (path: string, r: TutorResponse | undefined) => {
    if (!r) return
    responses.push([path, r])
    collect(`${path}.then`, r.then)
  }
  checks.forEach((c, i) => collect(`checks[${i}].respond`, c.respond))
  collect('showMe', scene.showMe)
  // The same object may appear in alternative responses (e.g. a misconception's and "show me"'s follow-up).
  const sceneIds = new Set(types.keys())
  for (const [path, r] of responses) {
    r.calls?.forEach((call, j) => {
      if (call.name !== 'add_object') return
      const spec = call.input.object
      if (types.has(spec.id) && !sceneIds.has(spec.id)) return
      checkObject(spec, `${path}.calls[${j}].object`, placed)
    })
  }

  const known = (id: string, path: string) => {
    if (types.has(id)) return true
    errors.push(`${path} refers to unknown object '${id}'`)
    return false
  }
  const portOf = (id: string, port: string) => modules[types.get(id)!]?.ports?.[port]

  scene.links?.forEach((l, i) => {
    known(l.from, `links[${i}].from`)
    known(l.to, `links[${i}].to`)
    if (!RELATIONS.includes(l.relation)) errors.push(`links[${i}].relation must be one of ${RELATIONS.join(', ')}`)
  })

  const checkPlug = (objectId: string, plug: string, to: { objectId: string; port: string } | null, path: string) => {
    if (!known(objectId, path)) return
    const p = portOf(objectId, plug)
    if (p?.role !== 'plug') return errors.push(`${path}: '${objectId}' has no plug '${plug}'`)
    if (!to || !known(to.objectId, `${path}.to`)) return
    const socket = portOf(to.objectId, to.port)
    if (socket?.role !== 'socket') errors.push(`${path}.to: '${to.objectId}' has no socket '${to.port}'`)
    else if (socket.kind !== p.kind) errors.push(`${path}.to: a ${p.kind} plug can't go into a ${socket.kind} socket`)
  }
  scene.wiring?.forEach((w, i) => checkPlug(w.plug.objectId, w.plug.port, w.to, `wiring[${i}]`))

  const ids = new Set<string>()
  checks.forEach((c, i) => {
    const path = `checks[${i}]`
    if (ids.has(c.id)) errors.push(`${path}.id '${c.id}' is used twice`)
    ids.add(c.id)
    if (!VERDICTS.includes(c.verdict)) errors.push(`${path}.verdict must be one of ${VERDICTS.join(', ')}`)
    if (!known(c.objectId, `${path}.objectId`)) return
    const observes = modules[types.get(c.objectId)!].about.observes
    if (!observes) return errors.push(`${path}: '${c.objectId}' (${types.get(c.objectId)}) has no checkable actions`)
    const bad = c.on.filter((a) => !observes.on.includes(a))
    if (bad.length) errors.push(`${path}.on: ${bad.join(', ')} can't be checked; use ${observes.on.join(', ')}`)
    for (const f of fieldsOf(c.when)) {
      if (!fieldAllowed(f, observes.fields)) errors.push(`${path}.when: unknown field '${f}' (known: ${Object.keys(observes.fields).join(', ')})`)
    }
    if (!c.silent && !c.explain?.trim()) errors.push(`${path}.explain is required unless the check is silent`)
  })
  if (!checks.some((c) => c.completesGoal)) errors.push('at least one check must have completesGoal: true')

  const checkDemoAction = (a: DemoAction, objectId: string, path: string) => {
    const target = a.objectId ?? objectId
    if (!known(target, path)) return
    const mod = modules[types.get(target)!]
    if (a.type === 'connect') return checkPlug(target, a.plug, a.to, path)
    if (a.type === 'swapPlugs') return a.plugs.forEach((p) => checkPlug(target, p, null, path))
    if (!(a.type in (mod.about.actions ?? {})) || WIRING_ACTIONS.includes(a.type))
      errors.push(`${path}: '${a.type}' is not an action of ${mod.type} (${Object.keys(mod.about.actions ?? {}).join(', ') || 'none'})`)
  }
  const checkCall = (call: ToolCall, path: string) => {
    switch (call.name) {
      case 'add_object':
      case 'get_canvas_state':
        return
      case 'open_playground':
        return errors.push(`${path}: a response can't open another scene`)
      case 'link':
        known(call.input.from, `${path}.from`)
        known(call.input.to, `${path}.to`)
        return
      case 'highlight':
      case 'update_config':
        known(call.input.objectId, `${path}.objectId`)
        return
      case 'edit_node':
        if (known(call.input.objectId, `${path}.objectId`) && types.get(call.input.objectId) !== 'code-graph')
          errors.push(`${path}: edit_node only works on a code-graph`)
        return
      case 'demonstrate':
        if (!known(call.input.objectId, `${path}.objectId`)) return
        if (!call.input.actions?.length) errors.push(`${path}.actions must not be empty`)
        call.input.actions?.forEach((a, k) => checkDemoAction(a, call.input.objectId, `${path}.actions[${k}]`))
        return
      default:
        errors.push(`${path}: unknown tool '${(call as { name: string }).name}'`)
    }
  }
  for (const [path, r] of responses) {
    if (!r.say?.trim()) errors.push(`${path}.say is required`)
    r.calls?.forEach((call, j) => checkCall(call, `${path}.calls[${j}]`))
  }

  return errors
}
