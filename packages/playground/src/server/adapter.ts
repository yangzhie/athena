import type { Action, Scene, ToolCall, ToolResult, RunResult } from '../contracts'
import { Playground } from '../core/store'
import { validateScene } from '../core/scene'
import { validate } from '../core/schema'
import { presetModules } from '../objects/registry'
import { AGENT_TOOLS } from '../contracts'
import { actionSchemas, CATALOG_VERSION } from './contract'

export type Checkpoint = ReturnType<Playground['checkpoint']>
export type Command =
  | { kind: 'open' | 'replace_confirmed'; scene: Scene }
  | { kind: 'action'; action: Action }
  | { kind: 'tool'; call: ToolCall }
  | { kind: 'accept' | 'reject'; proposal_id: string }
  | { kind: 'execution'; object_id: string; run_id: number; result: RunResult; actor: 'student' | 'agent' }

const modules = Object.fromEntries(presetModules.map((m) => [m.type, m]))
const check = (ok: unknown, error: string) => { if (!ok) throw new Error(error) }

function actionError(pg: Playground, action: Action): string | null {
  const obj = pg.getState().objects[action.objectId]
  if (!obj) return 'Unknown object'
  const mod = modules[obj.type]
  const { type, ...fields } = action
  delete (fields as Partial<Action>).objectId
  const schema = actionSchemas[type as keyof typeof actionSchemas]
  if (!schema) return 'Unsupported or transient action'
  if (type === 'connect') {
    const a = action as Extract<Action, { type: 'connect' }>
    if (a.to !== null && (typeof a.to !== 'object' || Array.isArray(a.to))) return 'Invalid port reference'
    const plug = mod.ports?.[a.plug]
    if (!plug || plug.role !== 'plug') return 'Unknown plug'
    if (a.to) {
      const target = pg.getState().objects[a.to.objectId]
      const port = target && modules[target.type].ports?.[a.to.port]
      if (!port || port.role !== 'socket' || port.kind !== plug.kind) return 'Incompatible socket'
    }
    return Object.keys(fields).some((key) => !['plug', 'to'].includes(key)) || !('to' in fields) ? 'Invalid connection' : null
  }
  const errors = validate(schema, fields, 'action')
  if (errors.length) return errors.join('; ')
  if (type === 'swapPlugs') {
    if (action.plugs.some((p) => mod.ports?.[p]?.role !== 'plug')) return 'Unknown plug'
  } else if (!mod.about.actions?.[type]) return 'Action is not supported by this object'
  return mod.validate?.(obj.state, action) ?? null
}

function safeScene(scene: Scene) {
  check(Array.isArray(scene?.objects) && scene.objects.length <= 24, 'Scene must have 1–24 objects')
  check(Array.isArray(scene.checks) && scene.checks.length <= 64, 'Scene checks must be an array of at most 64 checks')
  // A model cannot declare its invented output to be verified execution.
  for (const obj of scene.objects) check(obj.provenance !== 'real-run', 'Only verified execution may use real-run')
  const errors = validateScene(scene, presetModules)
  check(!errors.length, errors.join('; '))
}

/** Single source of behavior: the same store/reducers/validators used by LearningCanvas. */
export async function transition(checkpoint: Checkpoint | null, command?: Command) {
  const pg = new Playground(presetModules, { python: { provenance: 'real-run', run: async () => { throw new Error('Execution is provided by the private worker') } } }, true)
  if (checkpoint) pg.restore(checkpoint)
  const start = pg.getEvents().at(-1)?.seq ?? 0
  let result: ToolResult = { ok: true, status: 'done' }
  if (command?.kind === 'open' || command?.kind === 'replace_confirmed') {
    check(command.kind === 'replace_confirmed' || !checkpoint || !Object.values(pg.getState().objects).some((o) => o.modifiedBy === 'student'), 'Replacing student work requires an accepted replacement proposal')
    safeScene(command.scene)
    result = pg.open(command.scene)
  } else if (command?.kind === 'action') {
    const error = actionError(pg, command.action)
    check(!error, error ?? '')
    await pg.dispatch(command.action, 'student')
  } else if (command?.kind === 'execution') {
    const obj = pg.getState().objects[command.object_id]
    check(obj?.type === 'code-graph', 'Execution target must be a code graph')
    const state = obj.state as { running: boolean; runId: number }
    check(state.running && state.runId === command.run_id, 'Stale execution result')
    await pg.dispatch({ objectId: obj.id, type: 'runCompleted', runId: command.run_id, result: command.result } as Action, 'system', { onBehalfOf: command.actor })
  } else if (command?.kind === 'accept' || command?.kind === 'reject') {
    check(pg.getState().proposals.some((p) => p.id === command.proposal_id), 'Unknown proposal')
    if (command.kind === 'accept') await pg.acceptProposal(command.proposal_id)
    else await pg.rejectProposal(command.proposal_id)
  } else if (command?.kind === 'tool') {
    const call = command.call
    check(call && call.input && typeof call.input === 'object' && !Array.isArray(call.input), 'Invalid tool call')
    const definition = AGENT_TOOLS.find((tool) => tool.name === call.name)
    check(definition, 'Unknown tool')
    const shape = definition!.input_schema as { properties: Record<string, { type: string; enum?: string[] }>; required?: string[] }
    for (const field of shape.required ?? []) check(field in call.input, `Missing tool field: ${field}`)
    for (const [key, value] of Object.entries(call.input)) {
      const expected = shape.properties[key]
      check(expected, `Unknown tool field: ${key}`)
      check(expected.type === 'array' ? Array.isArray(value) : expected.type === 'object' ? !!value && typeof value === 'object' && !Array.isArray(value) : typeof value === expected.type, `Invalid tool field: ${key}`)
      if (expected.enum) check(expected.enum.includes(value as string), `Invalid tool field: ${key}`)
    }
    if (call.name === 'open_playground') {
      safeScene(call.input.scene)
      check(!Object.values(pg.getState().objects).some((o) => o.modifiedBy === 'student'), 'Replacing student work requires an accepted replacement proposal')
    } else if (call.name === 'demonstrate') {
      check(Array.isArray(call.input.actions) && call.input.actions.length <= 24, 'At most 24 demonstration actions')
      for (const a of call.input.actions) {
        const error = actionError(pg, { ...a, objectId: a.objectId ?? call.input.objectId } as Action)
        check(!error, error ?? '')
      }
    } else if (call.name === 'link') {
      check(['from', 'contrast', 'explains'].includes(call.input.relation), 'Unknown relation')
    } else if (call.name === 'add_object') {
      check(pg.getState().order.length < 24, 'Object limit reached')
      check(call.input.object.provenance !== 'real-run', 'Only verified execution may use real-run')
      check(!call.input.object.near || !!pg.getState().objects[call.input.object.near], 'Unknown placement reference')
    }
    const supported = ['open_playground', 'get_canvas_state', 'add_object', 'update_config', 'link', 'edit_node', 'demonstrate', 'highlight']
    check(supported.includes(call.name), 'Unknown tool')
    result = await pg.callTool(call)
    check(result?.ok, result && !result.ok ? result.error : 'Tool failed')
  }
  const pending_runs = Object.values(pg.getState().objects).flatMap((obj) => {
    if (obj.type !== 'code-graph') return []
    const s = obj.state as { running: boolean; runId: number; source: string }
    return s.running ? [{ object_id: obj.id, run_id: s.runId, source: s.source }] : []
  })
  const snapshot = pg.snapshot()
  check(new TextEncoder().encode(JSON.stringify(snapshot)).length <= 65536, 'Canvas snapshot exceeds 64 KiB')
  return { catalog_version: CATALOG_VERSION, checkpoint: pg.checkpoint(), snapshot, events: pg.getEvents().filter((e) => e.seq > start), result, pending_runs }
}
