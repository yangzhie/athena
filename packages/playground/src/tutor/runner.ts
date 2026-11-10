import type { CanvasSnapshot, ObjectId, Observation, PlaygroundEvent, Scene, ToolCall, ToolResult, TutorResponse } from '../contracts'
import type { Playground } from '../core/store'

export interface TutorMessage {
  text: string
  /** Tool calls made for this turn, in readable form. */
  tools?: string[]
  /** Where the reply came from: written with the scene, or asked of the model now. */
  origin?: 'prepared' | 'model'
}

/** Something the scene didn't prepare an answer for: the model's turn. */
export type TutorRequest =
  | { kind: 'question'; objectId: ObjectId | null; text: string; snapshot: CanvasSnapshot }
  | { kind: 'unmatched'; objectId: ObjectId; observation: Observation; snapshot: CanvasSnapshot }
  | { kind: 'misconception'; checkId: string; snapshot: CanvasSnapshot }

export interface TutorHooks {
  post(message: TutorMessage): void
  busy?(busy: boolean): void
  /** The model answers, optionally with tool calls on the canvas. */
  ask(request: TutorRequest): Promise<TutorResponse>
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/** Short, human-readable form of a tool call. */
export function describeCall(call: ToolCall): string {
  switch (call.name) {
    case 'open_playground':
      return `open_playground(${call.input.scene.id})`
    case 'add_object':
      return `add_object(${call.input.object.type}: ${call.input.object.id})`
    case 'edit_node':
      return `edit_node(${call.input.nodeId}, "${call.input.condition}")`
    case 'demonstrate':
      return `demonstrate(${call.input.objectId}, ${call.input.actions
        .map((a) => (a.type === 'connect' ? `${a.objectId ?? call.input.objectId}.${a.plug}→${a.to?.objectId ?? 'rest'}` : a.type))
        .join(' → ')})`
    case 'link':
      return `link(${call.input.from} → ${call.input.to}, ${call.input.relation})`
    case 'highlight':
      return `highlight(${call.input.objectId}${call.input.part ? `.${call.input.part}` : ''})`
    case 'update_config':
      return `update_config(${call.input.objectId})`
    case 'get_canvas_state':
      return 'get_canvas_state()'
  }
}

/** The object a call demonstrates on, if it starts a demonstration (now or once accepted). */
function demonstrationOf(call: ToolCall): ObjectId | null {
  if (call.name === 'demonstrate') return call.input.objectId
  if (call.name === 'edit_node' && call.input.demonstrateAfter) return call.input.objectId
  return null
}

/**
 * The tutor's side of a Playground. It knows nothing about any particular
 * scene: what to say and do for each check, "show me how" and follow-ups all
 * come from the scene, as the model wrote it. Anything the scene didn't
 * prepare (a free question, an unmatched action) goes to `hooks.ask`.
 */
export class TutorRunner {
  private pg: Playground
  private hooks: TutorHooks
  private current: Scene | null = null
  private answered = new Set<TutorResponse>()
  /** Topic answered last, so the same explanation isn't repeated back to back. */
  private lastTopic: string | null = null
  /** Follow-ups waiting for a demonstration the student has yet to accept, by object. */
  private pending = new Map<ObjectId, TutorResponse>()
  private queue: Promise<void> = Promise.resolve()

  constructor(pg: Playground, hooks: TutorHooks) {
    this.pg = pg
    this.hooks = hooks
  }

  /** Listen to the canvas. Returns the unsubscribe function. */
  start() {
    return this.pg.onEvent((e) => this.onEvent(e))
  }

  get scene() {
    return this.current
  }

  /** Open a scene with the tutor's opening message. Resolves with the tool result (errors list what to fix). */
  open(scene: Scene): Promise<ToolResult> {
    return new Promise((resolve) =>
      this.serial(async () => {
        this.current = scene
        this.answered.clear()
        this.pending.clear()
        this.lastTopic = null
        const [result] = await this.turn(scene.intro ?? `Let's try it on the Playground: ${scene.goal}.`, [{ name: 'open_playground', input: { scene } }])
        if (!result.ok) this.current = null
        resolve(result)
      }),
    )
  }

  /** The student asks to be shown the right way. False if the scene has no demonstration. */
  showMe() {
    const r = this.current?.showMe
    if (!r) return false
    this.serial(async () => {
      await sleep(500)
      await this.play(r)
    })
    return true
  }

  /** A question from the student, about an object or the canvas. */
  ask(objectId: ObjectId | null, text: string) {
    this.pg.discuss(objectId, text)
  }

  private serial(fn: () => Promise<void>) {
    this.queue = this.queue.then(async () => {
      this.hooks.busy?.(true)
      try {
        await fn()
      } finally {
        this.hooks.busy?.(false)
      }
    })
  }

  private async turn(text: string, calls: ToolCall[], origin?: TutorMessage['origin']) {
    const results: ToolResult[] = []
    this.hooks.post({ text, tools: calls.map(describeCall), origin })
    for (const call of calls) results.push(await this.pg.callTool(call))
    return results
  }

  private onEvent(e: PlaygroundEvent) {
    switch (e.kind) {
      case 'check': {
        const check = this.current?.checks.find((c) => c.id === e.checkId)
        if (check?.respond) this.serial(() => this.respond(check.respond!, check.id))
        else if (e.verdict === 'misconception') this.serial(() => this.model({ kind: 'misconception', checkId: e.checkId, snapshot: this.pg.snapshot() }))
        break
      }
      case 'unmatched':
        this.serial(() => this.model({ kind: 'unmatched', objectId: e.objectId, observation: e.observation, snapshot: this.pg.snapshot() }))
        break
      case 'goal-reached':
        // A goal check with its own response has already said what comes next.
        if (!this.current?.checks.find((c) => c.id === e.checkId)?.respond)
          this.serial(async () => {
            await sleep(400)
            this.hooks.post({ text: '🎉 Goal reached! Would your answer still hold with different data?' })
          })
        break
      case 'demonstration': {
        const then = e.status === 'finished' ? this.pending.get(e.objectId) : undefined
        if (then) {
          this.pending.delete(e.objectId)
          this.serial(async () => {
            await sleep(1200)
            await this.play(then)
          })
        }
        break
      }
      case 'proposal':
        if (e.status === 'rejected') {
          this.pending.delete(e.objectId)
          this.serial(async () => this.hooks.post({ text: 'OK, no change.' }))
        }
        break
      case 'discuss':
        this.serial(() => this.model({ kind: 'question', objectId: e.objectId, text: e.text, snapshot: this.pg.snapshot() }))
        break
    }
  }

  /** A check with a prepared response matched. */
  private async respond(r: TutorResponse, checkId: string) {
    const topic = r.topic ?? checkId
    if ((r.once ?? true) && this.answered.has(r)) return
    if (topic === this.lastTopic) return
    this.answered.add(r)
    this.lastTopic = topic
    await sleep(700)
    await this.play(r)
  }

  private async model(request: TutorRequest) {
    const r = await this.hooks.ask(request)
    await this.play(r, 'model')
  }

  /** Say the response, make its calls, and run its follow-up once its demonstration is over. */
  private async play(r: TutorResponse, origin: TutorMessage['origin'] = 'prepared') {
    const calls = r.calls ?? []
    // Already done before (e.g. the same note after a second demonstration).
    const adds = calls.flatMap((c) => (c.name === 'add_object' ? [c.input.object.id] : []))
    if (adds.length && adds.every((id) => this.pg.getState().objects[id])) return

    const results = await this.turn(r.say, calls, origin)
    const waiting = calls.findIndex((c, i) => demonstrationOf(c) && results[i]?.ok && results[i].status === 'needs-confirmation')
    if (waiting >= 0) {
      const call = calls[waiting]
      if (call.name === 'demonstrate') this.hooks.post({ text: 'This would clear your current attempt, so I’ve put it on the canvas for you to accept first.' })
      if (r.then) this.pending.set(demonstrationOf(call)!, r.then)
      return
    }
    if (r.then) {
      await sleep(1200)
      await this.play(r.then, origin)
    }
  }
}
