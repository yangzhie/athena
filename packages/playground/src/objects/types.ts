import type { ComponentType } from 'react'
import type { Schema } from '../core/schema'
import type {
  Actor,
  CodeRuntime,
  Feedback,
  Highlight,
  ObjectAction,
  ObjectConfigs,
  ObjectId,
  ObjectType,
  Observation,
  PortKind,
  PortRef,
  Provenance,
  Rect,
  SourceRef,
} from '../contracts'

/** An object as it lives on the canvas. */
export interface CanvasObject<T extends ObjectType = ObjectType, S = unknown> {
  id: ObjectId
  type: T
  title: string
  config: ObjectConfigs[T]
  provenance: Provenance
  sources?: SourceRef[]
  experimentId?: string
  rect: Rect
  state: S
  modifiedBy: Actor | null
  feedback: Feedback | null
  /** Where each of the object's plugs is attached (objects with plug ports only). */
  plugs: Record<string, PortRef | null>
  /** A plug tip being dragged by the virtual hand, in world coordinates. */
  plugDrag: { plug: string; x: number; y: number } | null
}

/** A port on an object, at a fixed position relative to the object's top-left corner. */
export interface PortSpec {
  kind: PortKind
  /** A plug is attached to a socket of the same kind on another object. */
  role: 'plug' | 'socket'
  /** Socket: where plugs attach. Plug: where its lead or tube leaves the object. */
  at: { x: number; y: number }
  /** Plug only: where the tip rests while unplugged. */
  rest?: { x: number; y: number }
  /** Plug only: how the connection is drawn. */
  look?: 'red' | 'black' | 'tube' | 'data'
  label?: string
  /** For the catalog: what the port is and what flows through it. */
  about?: string
}

/** What the model reads about an object type in the component catalog. */
export interface ModuleAbout {
  summary: string
  config: Schema
  /** Actions the agent can demonstrate on this object, each with a one-line description of its fields. */
  actions?: Record<string, string>
  /**
   * Fields checks can test after the listed actions (the action's own fields
   * are included). A field ending in ".*" stands for a family, e.g. "keeps.*".
   */
  observes?: { on: ObjectAction['type'][]; fields: Record<string, string> }
}

/** What an object sees of its connections. Read-only and computed on demand. */
export interface Wiring {
  /** The object this wiring belongs to. */
  self: ObjectId
  /** What is attached to one of this object's ports (for a plug, at most one socket). */
  peers(port: string): PortRef[]
  /** The value another object exposes through one of its ports. */
  read(ref: PortRef): unknown
}

export const NO_WIRING: Wiring = { self: '', peers: () => [], read: () => undefined }

export interface Runtimes {
  python: CodeRuntime
}

export interface ObjectViewProps<T extends ObjectType, S> {
  object: CanvasObject<T, S>
  state: S
  /** Commit a student action. */
  dispatch: (action: ObjectAction) => void
  /** Preview a student action mid-gesture: state updates live, but it isn't recorded or checked. */
  preview: (action: ObjectAction) => void
  /** The agent is replaying actions on this object. */
  demonstrating: boolean
  highlight: Highlight | null
  /** Other objects in the same experiment (same `experimentId`), e.g. a readout showing a lab's state. */
  peers: CanvasObject[]
  /** The object's connections through its ports. */
  wiring: Wiring
  /** Move the object (world coordinates of its top-left corner), e.g. dragging a piece of apparatus. */
  moveTo: (x: number, y: number) => void
}

/**
 * A preset object type. The Canvas core knows nothing about chemistry or code;
 * each type brings its own state, actions, observations and view.
 */
export interface ObjectModule<T extends ObjectType, S> {
  type: T
  /** Human label for the type, e.g. "Code graph". */
  label: string
  about: ModuleAbout
  /** Width of the slot the layout reserves for a new object. */
  width: number
  /**
   * Frameless objects live directly on the canvas (no card): their world
   * rectangle comes from their state, e.g. two atoms the student drags around.
   */
  bounds?(state: S): Rect
  /** Frameless objects only: move a freshly created state into the slot the layout picked. */
  placeAt?(state: S, x: number, y: number): S
  /**
   * Frameless objects of a fixed size, such as a piece of apparatus. They are
   * placed like cards and moved by dragging their body.
   */
  size?: { w: number; h: number }
  /** Typed ports other objects connect to. */
  ports?: Record<string, PortSpec>
  /** The value this object exposes through one of its ports. */
  read?(state: S, config: ObjectConfigs[T], port: string, wiring: Wiring): unknown
  init(config: ObjectConfigs[T]): S
  /** Pure state transition. Return `state` unchanged for actions that don't apply. */
  reduce(state: S, action: ObjectAction, config: ObjectConfigs[T], actor: Actor, wiring: Wiring): S
  /** Action types that change the object's content (for "who modified this"). */
  edits?: ObjectAction['type'][]
  /** Action types that throw away the student's work (e.g. emptying a flask); the agent must ask first. */
  resets?: ObjectAction['type'][]
  /** Facts for checks, after `reduce`. `null` = this action is not checked. */
  observe?(state: S, action: ObjectAction, config: ObjectConfigs[T], wiring: Wiring): Observation | null
  /** Async work an action triggers, such as running code. Resolves when done. */
  effect?(
    state: S,
    action: ObjectAction,
    ctx: { runtimes: Runtimes; dispatch: (action: ObjectAction) => void },
  ): Promise<void> | void
  /** Intermediate frames when the agent demonstrates an action (e.g. a drag). */
  tween?(state: S, action: ObjectAction): ObjectAction[]
  /** `data-anchor` part the virtual hand moves to for an action. */
  anchor?(action: ObjectAction, state: S): string
  /** Before/after preview for a proposed action. */
  preview?(state: S, action: ObjectAction): { before: string; after: string } | null
  /** Validate an action before it is proposed or applied; returns an error message. */
  validate?(state: S, action: ObjectAction): string | null
  /** Compact model-readable state for `get_canvas_state()`. */
  summarize(state: S, config: ObjectConfigs[T], wiring: Wiring): Record<string, unknown>
  View: ComponentType<ObjectViewProps<T, S>>
}

export type AnyModule = ObjectModule<ObjectType, unknown>

export function defineModule<T extends ObjectType, S>(m: ObjectModule<T, S>): AnyModule {
  return m as unknown as AnyModule
}
