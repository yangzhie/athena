import type {
  Action,
  Actor,
  CanvasSnapshot,
  Check,
  DemoAction,
  Highlight,
  Link,
  ObjectAction,
  ObjectId,
  ObjectSpec,
  ObjectType,
  PlaygroundEvent,
  PortRef,
  Proposal,
  Scene,
  ToolCall,
  ToolResult,
  Viewport,
} from '../contracts'
import { NO_WIRING, type AnyModule, type CanvasObject, type Runtimes, type Wiring } from '../objects/types'
import { matchCheck } from './checks'
import { bounds, fit, place, zoomAt } from './layout'
import { plugTip, portPoint, portSpec } from './ports'
import { validateScene } from './scene'
import { validate } from './schema'

export interface PlaygroundState {
  scene: Pick<Scene, 'id' | 'title' | 'goal'> | null
  objects: Record<ObjectId, CanvasObject>
  order: ObjectId[]
  links: Link[]
  checks: Check[]
  selection: ObjectId | null
  viewport: Viewport
  proposals: Proposal[]
  highlight: Highlight | null
  goalReached: boolean
  demonstrating: ObjectId | null
}

/** The agent's virtual hand, in screen pixels relative to the canvas element. */
export interface HandState {
  visible: boolean
  x: number
  y: number
  pressed: boolean
}

type DispatchOptions = {
  /** Intermediate demonstration frame: applied but not recorded or checked. */
  transient?: boolean
  demonstration?: boolean
  /** For system follow-ups (e.g. a run finishing): who started it. */
  onBehalfOf?: Actor
}

const EMPTY: PlaygroundState = {
  scene: null,
  objects: {},
  order: [],
  links: [],
  checks: [],
  selection: null,
  viewport: { x: 0, y: 0, zoom: 1 },
  proposals: [],
  highlight: null,
  goalReached: false,
  demonstrating: null,
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))
const ease = (t: number) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2)

/**
 * The Canvas controller. Hosts (the demo shell, later the tutor) hold one of
 * these, call its tools, and subscribe to its event stream; `LearningCanvas`
 * renders it.
 */
export class Playground {
  private state: PlaygroundState = EMPTY
  private listeners = new Set<() => void>()
  private hand: HandState = { visible: false, x: 0, y: 0, pressed: false }
  private handListeners = new Set<() => void>()
  private events: PlaygroundEvent[] = []
  private eventListeners = new Set<(e: PlaygroundEvent) => void>()
  private seq = 0
  private ids = 0
  private root: HTMLElement | null = null
  private highlightTimer: ReturnType<typeof setTimeout> | undefined
  /** Objects of a freshly opened scene still waiting for their real size; fit once all have one. */
  private unmeasured = new Set<ObjectId>()
  private modules: Record<string, AnyModule>
  private runtimes: Runtimes

  constructor(modules: AnyModule[], runtimes: Runtimes) {
    this.modules = Object.fromEntries(modules.map((m) => [m.type, m]))
    this.runtimes = runtimes
  }

  // ─── Subscriptions ──────────────────────────────────────────────────────

  getState = () => this.state
  subscribe = (l: () => void) => {
    this.listeners.add(l)
    return () => {
      this.listeners.delete(l)
    }
  }
  getHand = () => this.hand
  subscribeHand = (l: () => void) => {
    this.handListeners.add(l)
    return () => {
      this.handListeners.delete(l)
    }
  }
  getEvents = () => this.events
  onEvent = (l: (e: PlaygroundEvent) => void) => {
    this.eventListeners.add(l)
    return () => {
      this.eventListeners.delete(l)
    }
  }

  module(type: ObjectType) {
    return this.modules[type]
  }

  private moduleOf = (o: CanvasObject) => this.modules[o.type]

  /** Frameless objects take no card: they draw themselves straight onto the canvas. */
  private frameless(type: ObjectType) {
    const m = this.modules[type]
    return Boolean(m.bounds || m.size)
  }

  /**
   * What one object sees of its connections. Values are read on demand from
   * the current state, a few hops at most; nothing is scheduled.
   */
  wiring(id: ObjectId, depth = 0): Wiring {
    const obj = this.state.objects[id]
    if (!obj || !this.modules[obj.type].ports || depth > 6) return NO_WIRING
    return {
      self: id,
      peers: (port) => {
        const self = this.state.objects[id]
        const spec = self && this.modules[self.type].ports?.[port]
        if (!spec) return []
        if (spec.role === 'plug') {
          const to = self.plugs[port]
          return to && this.state.objects[to.objectId] ? [to] : []
        }
        return this.state.order.flatMap((oid) =>
          Object.entries(this.state.objects[oid].plugs)
            .filter(([, to]) => to?.objectId === id && to.port === port)
            .map(([plug]) => ({ objectId: oid, port: plug })),
        )
      },
      read: (ref) => {
        const o = this.state.objects[ref.objectId]
        return o && this.modules[o.type].read?.(o.state, o.config, ref.port, this.wiring(ref.objectId, depth + 1))
      },
    }
  }

  private set(patch: Partial<PlaygroundState>) {
    this.state = { ...this.state, ...patch }
    this.listeners.forEach((l) => l())
  }

  private patchObject(id: ObjectId, patch: Partial<CanvasObject>) {
    const obj = this.state.objects[id]
    if (!obj) return
    this.set({ objects: { ...this.state.objects, [id]: { ...obj, ...patch } } })
  }

  private setHand(patch: Partial<HandState>) {
    this.hand = { ...this.hand, ...patch }
    this.handListeners.forEach((l) => l())
  }

  private emit(e: DistributiveOmit<PlaygroundEvent, 'seq' | 'at'>) {
    const event = { ...e, seq: ++this.seq, at: Date.now() } as PlaygroundEvent
    this.events = [...this.events, event]
    this.eventListeners.forEach((l) => l(event))
  }

  private id(prefix: string) {
    return `${prefix}-${++this.ids}`
  }

  // ─── Host wiring (called by LearningCanvas) ─────────────────────────────

  attach(el: HTMLElement | null) {
    this.root = el
  }

  /** Container size in screen pixels, read live so it is never stale. */
  private get size() {
    return { w: this.root?.clientWidth || 1200, h: this.root?.clientHeight || 800 }
  }

  // ─── Student-facing operations ──────────────────────────────────────────

  /** Apply an action. Records it, runs checks for student actions and starts effects. */
  async dispatch(action: Action, actor: Actor = 'student', opts: DispatchOptions = {}): Promise<void> {
    const obj = this.state.objects[action.objectId]
    if (!obj) return
    const mod = this.modules[obj.type]
    // Plugs are generic: any object with plug ports can be connected and unplugged.
    if (action.type === 'swapPlugs') {
      const [a, b] = action.plugs
      if (mod.ports?.[a]?.role !== 'plug' || mod.ports?.[b]?.role !== 'plug') return
      this.patchObject(obj.id, { plugs: { ...obj.plugs, [a]: obj.plugs[b], [b]: obj.plugs[a] }, plugDrag: null })
    }
    if (action.type === 'connect' || action.type === 'dragPlug') {
      const spec = mod.ports?.[action.plug]
      if (spec?.role !== 'plug') return
      if (action.type === 'dragPlug') {
        this.patchObject(obj.id, { plugDrag: { plug: action.plug, x: action.x, y: action.y } })
        return
      }
      if (action.to && portSpec(this.state.objects, this.moduleOf, action.to)?.kind !== spec.kind) return
      this.patchObject(obj.id, { plugs: { ...obj.plugs, [action.plug]: action.to }, plugDrag: null })
    }
    const current = this.state.objects[obj.id]
    const state = mod.reduce(current.state, action, obj.config, opts.onBehalfOf ?? actor, this.wiring(obj.id))
    const edits = mod.edits?.includes(action.type) && actor !== 'system'
    // An edit makes earlier feedback stale; a student edit gets fresh feedback from its own check below.
    this.patchObject(obj.id, {
      state,
      ...(mod.bounds ? { rect: mod.bounds(state) } : {}),
      ...(edits && !opts.transient ? { modifiedBy: actor, feedback: null } : {}),
    })
    if (opts.transient) return

    this.emit({ kind: 'action', actor, action, ...(opts.demonstration ? { demonstration: true } : {}) })

    if ((opts.onBehalfOf ?? actor) === 'student') this.runChecks(action, state)

    if (mod.effect) {
      await mod.effect(state, action, {
        runtimes: this.runtimes,
        dispatch: (a) => this.dispatch({ ...a, objectId: obj.id }, 'system', { onBehalfOf: opts.onBehalfOf ?? actor }),
      })
    }
  }

  private runChecks(action: Action, state: unknown) {
    const obj = this.state.objects[action.objectId]
    const obs = this.modules[obj.type].observe?.(state, action, obj.config, this.wiring(obj.id))
    if (!obs) return
    const check = matchCheck(this.state.checks, action, obs)
    if (!check) {
      this.patchObject(obj.id, {
        feedback: { verdict: 'unmatched', text: 'No preset branch matched; handed to the tutor.', at: Date.now() },
      })
      this.emit({ kind: 'unmatched', objectId: obj.id, trigger: action, observation: obs })
      return
    }
    if (!check.silent) this.patchObject(obj.id, { feedback: { verdict: check.verdict, text: check.explain, at: Date.now() } })
    this.emit({
      kind: 'check',
      checkId: check.id,
      objectId: obj.id,
      verdict: check.verdict,
      explain: check.explain,
      trigger: action,
    })
    if (check.completesGoal && !this.state.goalReached) {
      this.set({ goalReached: true })
      this.emit({ kind: 'goal-reached', checkId: check.id })
    }
  }

  moveObject(id: ObjectId, x: number, y: number) {
    const obj = this.state.objects[id]
    if (obj) this.patchObject(id, { rect: { ...obj.rect, x, y } })
  }

  setObjectSize(id: ObjectId, w: number, h: number) {
    const obj = this.state.objects[id]
    if (!obj) return
    if (obj.rect.w !== w || obj.rect.h !== h) this.patchObject(id, { rect: { ...obj.rect, w, h } })
    if (this.unmeasured.delete(id) && this.unmeasured.size === 0) this.fitView()
  }

  select(id: ObjectId | null) {
    if (this.state.selection === id) return
    this.set({ selection: id })
    this.emit({ kind: 'selected', objectId: id })
  }

  removeObject(id: ObjectId, actor: Actor = 'student') {
    if (!this.state.objects[id]) return
    const objects = { ...this.state.objects }
    delete objects[id]
    // Whatever was plugged into the removed object hangs free again.
    for (const [oid, o] of Object.entries(objects)) {
      if (Object.values(o.plugs).some((to) => to?.objectId === id)) {
        objects[oid] = { ...o, plugs: Object.fromEntries(Object.entries(o.plugs).map(([p, to]) => [p, to?.objectId === id ? null : to])) }
      }
    }
    this.set({
      objects,
      order: this.state.order.filter((o) => o !== id),
      links: this.state.links.filter((l) => l.from !== id && l.to !== id),

      proposals: this.state.proposals.filter((p) => p.objectId !== id),
      selection: this.state.selection === id ? null : this.state.selection,
    })
    this.emit({ kind: 'object-removed', objectId: id, actor })
  }

  setViewport(viewport: Viewport) {
    this.set({ viewport })
  }

  zoomBy(factor: number, cx = this.size.w / 2, cy = this.size.h / 2) {
    this.set({ viewport: zoomAt(this.state.viewport, this.state.viewport.zoom * factor, cx, cy) })
  }

  fitView() {
    const b = bounds(this.state.order.map((id) => this.state.objects[id].rect))
    if (b) this.set({ viewport: fit(b, this.size) })
  }

  /** Bring objects into view (together), never zooming in past the current zoom. */
  focusObject(...ids: ObjectId[]) {
    const r = bounds(ids.map((id) => this.state.objects[id]?.rect).filter((x) => x !== undefined))
    if (!r) return
    const { x, y, zoom } = this.state.viewport
    const sx = r.x * zoom + x
    const sy = r.y * zoom + y
    const visible = sx >= 0 && sy >= 0 && sx + r.w * zoom <= this.size.w && sy + r.h * zoom <= this.size.h
    if (!visible) this.set({ viewport: fit(r, this.size, 48, zoom) })
  }

  acceptProposal(id: string) {
    const p = this.state.proposals.find((x) => x.id === id)
    if (!p) return
    this.set({ proposals: this.state.proposals.filter((x) => x.id !== id) })
    this.emit({ kind: 'proposal', proposalId: id, objectId: p.objectId, status: 'accepted' })
    if (p.config) this.applyConfig(p.objectId, p.config, 'agent')
    void (async () => {
      for (const a of p.actions) await this.dispatch(a, 'agent')
      if (p.thenDemonstrate?.length) await this.demonstrate(p.objectId, p.thenDemonstrate)
    })()
  }

  rejectProposal(id: string) {
    const p = this.state.proposals.find((x) => x.id === id)
    if (!p) return
    this.set({ proposals: this.state.proposals.filter((x) => x.id !== id) })
    this.emit({ kind: 'proposal', proposalId: id, objectId: p.objectId, status: 'rejected' })
  }

  /** The student asks about an object (or the canvas). The host forwards it to the tutor. */
  discuss(objectId: ObjectId | null, text: string) {
    this.emit({ kind: 'discuss', objectId, text })
  }

  // ─── Agent operations ────────────────────────────────────────────────────

  open(scene: Scene): ToolResult {
    const errors = validateScene(scene, Object.values(this.modules))
    if (errors.length) return { ok: false, error: `The scene is invalid:\n${errors.join('\n')}` }
    this.state = { ...EMPTY, viewport: this.state.viewport }
    this.set({ scene: { id: scene.id, title: scene.title, goal: scene.goal }, checks: scene.checks })
    for (const spec of scene.objects) this.addObject(spec, 'agent', false)
    for (const l of scene.links ?? []) this.addLink(l.from, l.to, l.relation, 'agent', false)
    for (const w of scene.wiring ?? []) {
      const o = this.state.objects[w.plug.objectId]
      if (o && this.modules[o.type].ports?.[w.plug.port]) this.patchObject(o.id, { plugs: { ...o.plugs, [w.plug.port]: w.to } })
    }
    this.emit({ kind: 'scene-opened', sceneId: scene.id })
    // Frameless objects know their size; cards have to be measured first.
    this.unmeasured = new Set(this.state.order.filter((id) => !this.frameless(this.state.objects[id].type)))
    this.fitView()
    return { ok: true, status: 'done' }
  }

  addObject(spec: ObjectSpec, actor: Actor = 'agent', emit = true): ToolResult {
    const mod = this.modules[spec.type]
    if (!mod) return { ok: false, error: `unknown object type '${spec.type}'` }
    if (this.state.objects[spec.id]) return { ok: false, error: `object '${spec.id}' already exists` }
    const invalid = validate(mod.about.config, spec.config, `${spec.id}.config`)
    if (invalid.length) return { ok: false, error: invalid.join('\n') }
    const rects = this.state.order.map((id) => this.state.objects[id].rect)
    const anchorId = spec.near ?? this.state.selection
    const anchor = anchorId ? (this.state.objects[anchorId]?.rect ?? null) : null
    const slot = place(mod.size?.w ?? mod.width, rects, anchor, spec.side, mod.size?.h)
    const state = mod.placeAt ? mod.placeAt(mod.init(spec.config), slot.x, slot.y) : mod.init(spec.config)
    const obj: CanvasObject = {
      id: spec.id,
      type: spec.type,
      title: spec.title,
      config: spec.config,
      provenance: spec.provenance,
      sources: spec.sources,
      experimentId: spec.experimentId,
      rect: mod.bounds ? mod.bounds(state) : slot,
      state,
      modifiedBy: null,
      feedback: null,
      plugs: Object.fromEntries(
        Object.entries(mod.ports ?? {})
          .filter(([, p]) => p.role === 'plug')
          .map(([id]) => [id, null]),
      ),
      plugDrag: null,
    }
    this.set({ objects: { ...this.state.objects, [obj.id]: obj }, order: [...this.state.order, obj.id] })
    if (emit) {
      this.emit({ kind: 'object-added', objectId: obj.id, actor })
      this.focusObject(obj.id, ...(anchorId && this.state.objects[anchorId] ? [anchorId] : []))
    }
    return { ok: true, status: 'done' }
  }

  addLink(from: ObjectId, to: ObjectId, relation: Link['relation'], actor: Actor = 'agent', emit = true): ToolResult {
    if (!this.state.objects[from] || !this.state.objects[to]) return { ok: false, error: 'unknown object' }
    const link: Link = { id: this.id('link'), from, to, relation }
    this.set({ links: [...this.state.links, link] })
    if (emit) this.emit({ kind: 'linked', link, actor })
    return { ok: true, status: 'done' }
  }

  private applyConfig(id: ObjectId, config: Record<string, unknown>, actor: Actor) {
    const obj = this.state.objects[id]
    const next = { ...obj.config, ...config } as typeof obj.config
    const mod = this.modules[obj.type]
    const state = mod.placeAt ? mod.placeAt(mod.init(next), obj.rect.x, obj.rect.y) : mod.init(next)
    this.patchObject(id, {
      config: next,
      state,
      ...(mod.bounds ? { rect: mod.bounds(state) } : {}),
      modifiedBy: actor,
      feedback: null,
    })
  }

  private propose(p: Omit<Proposal, 'id'>): ToolResult {
    const proposal = { ...p, id: this.id('proposal') }
    this.set({ proposals: [...this.state.proposals.filter((x) => x.objectId !== p.objectId), proposal] })
    this.emit({ kind: 'proposal', proposalId: proposal.id, objectId: p.objectId, status: 'pending' })
    this.focusObject(p.objectId)
    return { ok: true, status: 'needs-confirmation', proposalId: proposal.id }
  }

  highlightPart(h: Highlight) {
    clearTimeout(this.highlightTimer)
    this.set({ highlight: h })
    this.focusObject(h.objectId)
    this.highlightTimer = setTimeout(() => this.set({ highlight: null }), 6000)
  }

  /**
   * Replay actions with the virtual hand. Each committed action is a normal
   * (agent) event. An action may name another object, so one demonstration can
   * work across components, e.g. plug a lead into an electrode, then record.
   */
  async demonstrate(objectId: ObjectId, actions: DemoAction[]): Promise<ToolResult> {
    if (this.state.demonstrating) return { ok: false, error: 'a demonstration is already running' }
    if (!this.state.objects[objectId]) return { ok: false, error: `unknown object '${objectId}'` }
    const targets = new Set([objectId])
    for (const a of actions) {
      if (a.objectId) targets.add(a.objectId)
      if (a.type === 'connect' && a.to) targets.add(a.to.objectId)
    }
    this.focusObject(...targets)
    this.set({ demonstrating: objectId })
    this.emit({ kind: 'demonstration', objectId, status: 'started' })
    await sleep(250)
    try {
      // Swapping two plugs is shown as two moves of the hand.
      const steps = actions.flatMap((a): DemoAction[] => {
        if (a.type !== 'swapPlugs') return [a]
        const obj = this.state.objects[a.objectId ?? objectId]
        const [p, q] = a.plugs
        if (!obj) return []
        return [
          { objectId: obj.id, type: 'connect', plug: p, to: obj.plugs[q] ?? null },
          { objectId: obj.id, type: 'connect', plug: q, to: obj.plugs[p] ?? null },
        ]
      })
      for (const { objectId: other, ...a } of steps) {
        const target = other ?? objectId
        const obj = this.state.objects[target]
        if (!obj) break
        this.set({ demonstrating: target })
        const mod = this.modules[obj.type]
        const part = a.type === 'connect' || a.type === 'dragPlug' ? `plug:${a.plug}` : (mod.anchor?.(a, obj.state) ?? 'body')
        await this.moveHand(target, part, 650)
        this.setHand({ pressed: true })
        await sleep(160)
        const frames = a.type === 'connect' ? this.plugFrames(obj, a.plug, a.to) : (mod.tween?.(obj.state, a) ?? [])
        for (const frame of frames) {
          await this.dispatch({ ...frame, objectId: target }, 'agent', { transient: true })
          await sleep(16)
          this.snapHand(target, part)
        }
        await this.dispatch({ ...a, objectId: target } as Action, 'agent', { demonstration: true })
        this.snapHand(target, part)
        this.setHand({ pressed: false })
        await sleep(450)
      }
    } finally {
      this.setHand({ visible: false, pressed: false })
      this.set({ demonstrating: null })
      this.emit({ kind: 'demonstration', objectId, status: 'finished' })
    }
    return { ok: true, status: 'done' }
  }

  /** The tip of a plug travelling to its new socket (or back to rest). */
  private plugFrames(obj: CanvasObject, plug: string, to: PortRef | null): ObjectAction[] {
    const spec = this.modules[obj.type].ports?.[plug]
    if (!spec) return []
    const from = plugTip(this.state.objects, this.moduleOf, obj, plug)
    const end = (to && portPoint(this.state.objects, this.moduleOf, to)) ?? { x: obj.rect.x + (spec.rest ?? spec.at).x, y: obj.rect.y + (spec.rest ?? spec.at).y }
    const n = 40
    return Array.from({ length: n }, (_, i) => {
      const k = ease((i + 1) / n)
      // Lift the plug a little on the way, as a hand would.
      const lift = Math.sin(k * Math.PI) * 40
      return { type: 'dragPlug' as const, plug, x: from.x + (end.x - from.x) * k, y: from.y + (end.y - from.y) * k - lift }
    })
  }

  private anchorPoint(objectId: ObjectId, part: string) {
    if (!this.root) return null
    const el =
      this.root.querySelector(`[data-anchor="${CSS.escape(`${objectId}/${part}`)}"]`) ??
      this.root.querySelector(`[data-object="${CSS.escape(objectId)}"]`)
    if (!el) return null
    const r = el.getBoundingClientRect()
    const root = this.root.getBoundingClientRect()
    return { x: r.left + r.width / 2 - root.left, y: r.top + r.height / 2 - root.top }
  }

  private snapHand(objectId: ObjectId, part: string) {
    const p = this.anchorPoint(objectId, part)
    if (p) this.setHand(p)
  }

  private moveHand(objectId: ObjectId, part: string, ms: number) {
    const target = this.anchorPoint(objectId, part)
    if (!target) return Promise.resolve()
    const from = this.hand.visible ? { x: this.hand.x, y: this.hand.y } : { x: target.x + 140, y: target.y + 120 }
    this.setHand({ visible: true, ...from })
    const t0 = performance.now()
    return new Promise<void>((resolve) => {
      const step = (now: number) => {
        const t = Math.min(1, (now - t0) / ms)
        const k = ease(t)
        this.setHand({ x: from.x + (target.x - from.x) * k, y: from.y + (target.y - from.y) * k })
        if (t < 1) requestAnimationFrame(step)
        else resolve()
      }
      requestAnimationFrame(step)
    })
  }

  snapshot(): CanvasSnapshot {
    const s = this.state
    return {
      scene: s.scene,
      goalReached: s.goalReached,
      selection: s.selection,
      objects: s.order.map((id) => {
        const o = s.objects[id]
        return {
          id,
          type: o.type,
          title: o.title,
          provenance: o.provenance,
          modifiedBy: o.modifiedBy,
          state: this.modules[o.type].summarize(o.state, o.config, this.wiring(id)),
          feedback: o.feedback,
          ...(Object.keys(o.plugs).length ? { plugs: o.plugs } : {}),
        }
      }),
      links: s.links,
      pendingProposals: s.proposals.map(({ id, objectId, summary }) => ({ id, objectId, summary })),
      recentEvents: this.events.slice(-15),
    }
  }

  /** The agent's single entry point. Mirrors `AGENT_TOOLS`. */
  async callTool(call: ToolCall): Promise<ToolResult> {
    switch (call.name) {
      case 'open_playground':
        return this.open(call.input.scene)
      case 'get_canvas_state':
        return { ok: true, status: 'done', data: this.snapshot() }
      case 'add_object':
        return this.addObject(call.input.object, 'agent')
      case 'link':
        return this.addLink(call.input.from, call.input.to, call.input.relation, 'agent')
      case 'update_config': {
        const obj = this.state.objects[call.input.objectId]
        if (!obj) return { ok: false, error: `unknown object '${call.input.objectId}'` }
        if (obj.modifiedBy === 'student') {
          return this.propose({ objectId: obj.id, summary: call.input.reason, actions: [], config: call.input.config })
        }
        this.applyConfig(obj.id, call.input.config, 'agent')
        return { ok: true, status: 'done' }
      }
      case 'edit_node': {
        const { objectId, nodeId, condition, reason, demonstrateAfter } = call.input
        const obj = this.state.objects[objectId]
        if (!obj || obj.type !== 'code-graph') return { ok: false, error: `'${objectId}' is not a code graph` }
        const mod = this.modules[obj.type]
        const action: Action = { type: 'editCondition', nodeId, condition, objectId }
        const error = mod.validate?.(obj.state, action)
        if (error) return { ok: false, error }
        return this.propose({
          objectId,
          summary: reason,
          diff: mod.preview?.(obj.state, action) ?? undefined,
          actions: [action],
          thenDemonstrate: demonstrateAfter ? [{ type: 'run' }] : undefined,
        })
      }
      case 'demonstrate': {
        const { objectId, actions } = call.input
        const obj = this.state.objects[objectId]
        if (!obj) return { ok: false, error: `unknown object '${objectId}'` }
        const resets = this.modules[obj.type].resets ?? []
        // Replaying on top of the student's own work would throw it away: ask first.
        if (obj.modifiedBy === 'student' && actions.some((a) => resets.includes(a.type))) {
          return this.propose({
            objectId,
            summary: 'show you the technique on a fresh start (this clears your current attempt)',
            actions: [],
            thenDemonstrate: actions,
          })
        }
        return this.demonstrate(objectId, actions)
      }
      case 'highlight': {
        if (!this.state.objects[call.input.objectId]) return { ok: false, error: 'unknown object' }
        this.highlightPart(call.input)
        return { ok: true, status: 'done' }
      }
    }
  }
}

type DistributiveOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never

export function createPlayground(opts: { modules: AnyModule[]; runtimes: Runtimes }) {
  return new Playground(opts.modules, opts.runtimes)
}
