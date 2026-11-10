/**
 * Playground Canvas contracts.
 *
 * Everything that crosses the boundary between the Canvas and its host (the
 * demo shell today, the Athena tutor later) is defined here: scenes, objects,
 * actions, links, checks, events, the canvas snapshot and the agent tools.
 *
 * One action model drives everything. A student's gesture, an agent tool call
 * and a demonstration replay all dispatch the same `Action`; every committed
 * action is also an event on the event stream.
 */

export type ObjectId = string
export type Actor = 'student' | 'agent' | 'system'

/**
 * Where a piece of content comes from. The UI labels each one differently so
 * that an AI estimate is never mistaken for a real run.
 */
export type Provenance =
  | 'real-run' // executed for real (Pyodide in the browser)
  | 'simulated' // computed by a JS stand-in for the real runtime
  | 'ai-estimate' // numbers the AI produced when generating the scene
  | 'concept' // conceptual illustration, not a measurement
  | 'material' // taken from the unit's material

export interface SourceRef {
  label: string // e.g. "Week 3 slides, p. 12"
  href?: string
}

// ─── Objects ────────────────────────────────────────────────────────────────

export interface NoteConfig {
  markdown: string
}

export interface CodeGraphConfig {
  language: 'python'
  /** The source is the only truth; the node graph is derived from it. */
  source: string
  /** Values the student can drag onto a node to probe it, as Python literals. */
  probeValues: string[]
}

export interface ForceCurvePoint {
  /** Distance between the two particles, in nm. */
  r: number
  /** Net force; positive = repulsion, negative = attraction. */
  f: number
}

export interface ForceLabConfig {
  particles: [ParticleSpec, ParticleSpec]
  /** Key points produced once when the scene was generated; interpolated locally. */
  curve: ForceCurvePoint[]
  forceUnit: string
  range: [number, number]
  initialDistance: number
}

export interface ParticleSpec {
  label: string
  color: string
  radius: number // drawing radius in nm (visual only)
}

export interface ResultConfig {
  /** Fixed rows, e.g. values the scene already knows. */
  rows?: { label: string; value: string; note?: string }[]
  /** Or compare the last two runs of the code graph in the same experiment, live. */
  compareRuns?: { value: string; also?: string }
  caption?: string
}

/** Shows the live state of a force lab in the same experiment (same `experimentId`). */
export type ForceReadoutConfig = Record<string, never>

/**
 * An acid–base titration rig: a burette of base over a flask of acid with an
 * indicator. Concentrations are chosen when the scene is generated; pH and
 * colour come from an ideal strong acid / strong base model computed locally.
 */
export interface TitrationConfig {
  analyte: { formula: string; concentration: number; volume: number } // mol/L, mL (in the flask)
  titrant: { formula: string; concentration: number; label: string } // the true concentration is hidden from the student
  indicator: { name: string; transition: [number, number] } // pH range where the colour appears
  burette: { capacity: number; dropVolume: number } // mL
}

/** Shows readings, recorded trials and the titration curve of the rig in the same experiment. */
export type TitrationReadoutConfig = Record<string, never>

// ─── Galvanic cell bench: independent components wired together ─────────────

/** One half-cell: a metal electrode in a solution of its ions. */
export interface HalfCellConfig {
  metal: string // e.g. "Zn"
  ion: string // e.g. "Zn²⁺"
  electrons: number // n in M^n+ + n e⁻ → M
  standardPotential: number // E° vs SHE, in V
  concentration: number // mol/L of the ion at the start
  solutionColor: string // CSS colour of the solution
}

export interface SaltBridgeConfig {
  electrolyte: string // e.g. "KNO₃"
}

export type VoltmeterConfig = Record<string, never>

/** Records readings from whatever instrument is plugged into it. */
export type PotentialLogConfig = Record<string, never>

export interface ObjectConfigs {
  note: NoteConfig
  'code-graph': CodeGraphConfig
  'force-lab': ForceLabConfig
  'force-readout': ForceReadoutConfig
  titration: TitrationConfig
  'titration-readout': TitrationReadoutConfig
  result: ResultConfig
  'half-cell': HalfCellConfig
  'salt-bridge': SaltBridgeConfig
  voltmeter: VoltmeterConfig
  'potential-log': PotentialLogConfig
}

export type ObjectType = keyof ObjectConfigs

/** An object as a scene or the agent describes it. The Canvas decides its position. */
export type ObjectSpec = {
  [T in ObjectType]: {
    id: ObjectId
    type: T
    title: string
    config: ObjectConfigs[T]
    provenance: Provenance
    sources?: SourceRef[]
    /** Objects with the same experiment id share state (e.g. a run and its result). */
    experimentId?: string
    /** Place the new object next to this one. */
    near?: ObjectId
    /** Which side of `near` (default right). */
    side?: 'right' | 'below'
  }
}[ObjectType]

// ─── Links ─────────────────────────────────────────────────────────────────

/** A small, fixed set of typed relations. Links are drawn, never executed. */
export type Relation = 'from' | 'contrast' | 'explains'

export interface Link {
  id: string
  from: ObjectId
  to: ObjectId
  relation: Relation
}

// ─── Ports ─────────────────────────────────────────────────────────────────

/**
 * Components are independent: each owns its own state and exposes typed ports.
 * A plug (a lead, a salt-bridge end, a data cable) is attached to a socket of
 * the same kind on another object. Values are read through the connection;
 * nothing is scheduled or executed.
 */
export type PortKind = 'lead' | 'bridge' | 'data'

export interface PortRef {
  objectId: ObjectId
  port: string
}

// ─── Actions ───────────────────────────────────────────────────────────────

/** Actions any object with plugs understands. */
export type WiringAction =
  | { type: 'connect'; plug: string; to: PortRef | null } // null = unplug
  | { type: 'dragPlug'; plug: string; x: number; y: number } // plug tip in world coordinates mid-drag (preview only)
  | { type: 'swapPlugs'; plugs: [string, string] } // e.g. swap a meter's two leads

/** Actions on a code graph. Node ids are the names the source assigns. */
export type CodeGraphAction =
  | { type: 'probe'; nodeId: string; value: string }
  | { type: 'editCondition'; nodeId: string; condition: string }
  | { type: 'run' }
  | { type: 'runCompleted'; runId: number; result: RunResult }

/**
 * Actions on a force lab. The student drags either particle anywhere on the
 * canvas (`moveParticle`, world coordinates); the agent usually uses
 * `setDistance`, which moves the second particle along the line between them.
 */
export type ForceLabAction =
  | { type: 'moveParticle'; index: 0 | 1; x: number; y: number }
  | { type: 'setDistance'; distance: number }

/**
 * Actions on a titration rig. Students turn the tap (`setTap`, 0 closed … 1
 * fully open), swirl the flask by shaking it (`wobble` frames, then `swirl`)
 * and record the endpoint. The agent usually dispenses with `dispenseTo`.
 */
export type TitrationAction =
  | { type: 'setTap'; opening: number }
  | { type: 'tick'; dt: number } // time passing while the tap is open (preview only)
  | { type: 'dispenseTo'; volume: number; mode: 'stream' | 'dropwise' }
  | { type: 'wobble'; dx: number } // flask displacement while being shaken (preview only)
  | { type: 'swirl' }
  | { type: 'recordEndpoint' }
  | { type: 'newTrial' }

/** Actions on the galvanic cell components. */
export type GalvanicAction =
  | { type: 'dilute' } // half-cell: dilute the solution tenfold
  | { type: 'refill' } // half-cell: back to the starting concentration
  | { type: 'recordReading' } // potential log: record what the connected meter shows

export type ObjectAction = CodeGraphAction | ForceLabAction | TitrationAction | GalvanicAction | WiringAction

/** An action for a demonstration step; `objectId` targets another object than the demonstration's own. */
export type DemoAction = ObjectAction & { objectId?: ObjectId }

/** An action targeted at one object. */
export type Action = ObjectAction & { objectId: ObjectId }

/** Narrow an `Action` to one `type`. */
export type ActionOf<T extends Action['type']> = Extract<Action, { type: T }>

// ─── Runtime ───────────────────────────────────────────────────────────────

export type TraceStep =
  | { kind: 'iterate'; nodeId: string; value: string; kept: boolean | 'error' }
  | { kind: 'assign'; nodeId: string; value: string }
  | { kind: 'error'; nodeId: string; message: string }

export interface RunResult {
  ok: boolean
  provenance: Extract<Provenance, 'real-run' | 'simulated'>
  stdout: string
  /** Final value of each top-level name, as Python reprs. */
  values: Record<string, string>
  trace: TraceStep[]
  error?: { type: string; message: string; nodeId?: string }
}

/** Executes code for code objects. The Canvas never assumes a backend. */
export interface CodeRuntime {
  readonly provenance: RunResult['provenance']
  run(source: string): Promise<RunResult>
}

// ─── Checks and misconception branches ─────────────────────────────────────

/**
 * Everything a check can look at after an action: the action's own fields plus
 * whatever the object module observes (e.g. `kept`, `regime`, `keeps.0`).
 */
export type Observation = Record<string, string | number | boolean | null>

export type Condition =
  | { field: string; op: 'eq' | 'ne'; value: string | number | boolean | null }
  | { field: string; op: 'lt' | 'lte' | 'gt' | 'gte'; value: number }
  | { field: string; op: 'between'; value: [number, number] }
  | { field: string; op: 'oneOf'; value: (string | number | boolean | null)[] }
  | { all: Condition[] }
  | { any: Condition[] }

export type Verdict = 'correct' | 'hint' | 'misconception'

/**
 * Written when the scene is generated and matched locally at runtime, so the
 * student gets feedback immediately. Only misconceptions, questions and
 * unmatched actions are handed to the model.
 */
export interface Check {
  id: string
  objectId: ObjectId
  on: Action['type'][]
  when: Condition
  verdict: Verdict
  /** Shown on the object straight away. */
  explain: string
  /** Matching this check completes the scene goal. */
  completesGoal?: boolean
  /** An expected, unremarkable branch: recorded as an event but shows no feedback. */
  silent?: boolean
  /** What the tutor says and does when this check matches, written with the scene. */
  respond?: TutorResponse
}

/**
 * A tutor turn prepared when the scene is generated: a chat message plus tool
 * calls run in order (a demonstration finishes before the next call starts).
 * The Canvas ignores these; the tutor runtime plays them back, so the common
 * branches need no model call at all.
 */
export interface TutorResponse {
  say: string
  calls?: ToolCall[]
  /** Answer only the first time (default true for checks). */
  once?: boolean
  /** Responses with the same topic aren't repeated back to back (default: the check id). */
  topic?: string
  /**
   * Follow-up once the demonstration these calls start has finished, including
   * one the student first had to accept (e.g. add a note explaining what they saw).
   */
  then?: TutorResponse
}

// ─── Scene ─────────────────────────────────────────────────────────────────

export interface Scene {
  id: string
  title: string
  goal: string
  objects: ObjectSpec[]
  links?: Omit<Link, 'id'>[]
  /** Plugs already attached when the scene opens, e.g. a meter's data cable into its log. */
  wiring?: { plug: PortRef; to: PortRef }[]
  checks: Check[]
  /** The tutor's message when it opens the scene. */
  intro?: string
  /** What the tutor does when the student asks to be shown the right way. */
  showMe?: TutorResponse
}

// ─── Canvas state ──────────────────────────────────────────────────────────

export interface Rect {
  x: number
  y: number
  w: number
  h: number
}

export interface Viewport {
  x: number // screen offset of world origin
  y: number
  zoom: number
}

export interface Feedback {
  verdict: Verdict | 'unmatched'
  text: string
  at: number
}

/** A change the agent wants to make. Shown with a diff; the student decides. */
export interface Proposal {
  id: string
  objectId: ObjectId
  summary: string
  diff?: { before: string; after: string }
  /** Applied as agent actions on accept. */
  actions: Action[]
  /** Or a config replacement (update_config on an object the student changed). */
  config?: Record<string, unknown>
  /** Run this demonstration once the student accepts. */
  thenDemonstrate?: DemoAction[]
}

export interface Highlight {
  objectId: ObjectId
  part?: string
  note?: string
}

/** What the agent reads with `get_canvas_state()`. */
export interface CanvasSnapshot {
  scene: Pick<Scene, 'id' | 'title' | 'goal'> | null
  goalReached: boolean
  selection: ObjectId | null
  objects: {
    id: ObjectId
    type: ObjectType
    title: string
    provenance: Provenance
    /** Who last changed the object's content. */
    modifiedBy: Actor | null
    /** A compact, model-readable view of the object's current state. */
    state: Record<string, unknown>
    /** Where this object's plugs are attached. */
    plugs?: Record<string, PortRef | null>
    feedback: Feedback | null
  }[]
  links: Link[]
  pendingProposals: Pick<Proposal, 'id' | 'objectId' | 'summary'>[]
  recentEvents: PlaygroundEvent[]
}

// ─── Events ────────────────────────────────────────────────────────────────

type EventBase = { seq: number; at: number }

/** The Canvas's event stream. The host (demo shell, later the tutor) subscribes. */
export type PlaygroundEvent = EventBase &
  (
    | { kind: 'scene-opened'; sceneId: string }
    | { kind: 'action'; actor: Actor; action: Action; demonstration?: boolean }
    | { kind: 'check'; checkId: string; objectId: ObjectId; verdict: Verdict; explain: string; trigger: Action }
    | { kind: 'unmatched'; objectId: ObjectId; trigger: Action; observation: Observation }
    | { kind: 'goal-reached'; checkId: string }
    | { kind: 'object-added'; objectId: ObjectId; actor: Actor }
    | { kind: 'object-removed'; objectId: ObjectId; actor: Actor }
    | { kind: 'linked'; link: Link; actor: Actor }
    | { kind: 'selected'; objectId: ObjectId | null }
    | { kind: 'proposal'; proposalId: string; objectId: ObjectId; status: 'pending' | 'accepted' | 'rejected' }
    | { kind: 'demonstration'; objectId: ObjectId; status: 'started' | 'finished' }
    | { kind: 'discuss'; objectId: ObjectId | null; text: string }
  )

export type PlaygroundEventKind = PlaygroundEvent['kind']

// ─── Agent tools ───────────────────────────────────────────────────────────

export type ToolCall =
  | { name: 'open_playground'; input: { scene: Scene } }
  | { name: 'get_canvas_state'; input: Record<string, never> }
  | { name: 'add_object'; input: { object: ObjectSpec } }
  | { name: 'update_config'; input: { objectId: ObjectId; config: Record<string, unknown>; reason: string } }
  | { name: 'link'; input: { from: ObjectId; to: ObjectId; relation: Relation } }
  | {
      name: 'edit_node'
      input: { objectId: ObjectId; nodeId: string; condition: string; reason: string; demonstrateAfter?: boolean }
    }
  | { name: 'demonstrate'; input: { objectId: ObjectId; actions: DemoAction[] } }
  | { name: 'highlight'; input: { objectId: ObjectId; part?: string; note?: string } }

export type ToolName = ToolCall['name']

export type ToolResult =
  | { ok: true; status: 'done'; data?: unknown }
  | { ok: true; status: 'needs-confirmation'; proposalId: string }
  | { ok: false; error: string }

/** JSON-schema tool definitions to hand to a model. Mirrors `ToolCall`. */
export const AGENT_TOOLS: { name: ToolName; description: string; input_schema: Record<string, unknown> }[] = [
  {
    name: 'open_playground',
    description:
      'Open the Playground with a scene: the goal, the objects (pick from the preset object types and fill in their config), typed links between them, and the checks including likely misconception branches.',
    input_schema: { type: 'object', properties: { scene: { type: 'object' } }, required: ['scene'] },
  },
  {
    name: 'get_canvas_state',
    description: "Read the canvas: objects with their current state, who changed them, feedback, selection and recent events.",
    input_schema: { type: 'object', properties: {} },
  },
  {
    name: 'add_object',
    description: 'Add one object near a related one. Do not give coordinates.',
    input_schema: { type: 'object', properties: { object: { type: 'object' } }, required: ['object'] },
  },
  {
    name: 'update_config',
    description:
      "Change an object's config. If the student has changed that object, the student is asked to confirm first.",
    input_schema: {
      type: 'object',
      properties: { objectId: { type: 'string' }, config: { type: 'object' }, reason: { type: 'string' } },
      required: ['objectId', 'config', 'reason'],
    },
  },
  {
    name: 'link',
    description: 'Draw a typed link between two objects.',
    input_schema: {
      type: 'object',
      properties: {
        from: { type: 'string' },
        to: { type: 'string' },
        relation: { type: 'string', enum: ['from', 'contrast', 'explains'] },
      },
      required: ['from', 'to', 'relation'],
    },
  },
  {
    name: 'edit_node',
    description:
      'Propose a structured edit to a code-graph node (its filter condition). The student sees a diff and accepts or rejects it.',
    input_schema: {
      type: 'object',
      properties: {
        objectId: { type: 'string' },
        nodeId: { type: 'string' },
        condition: { type: 'string' },
        reason: { type: 'string' },
        demonstrateAfter: { type: 'boolean' },
      },
      required: ['objectId', 'nodeId', 'condition', 'reason'],
    },
  },
  {
    name: 'demonstrate',
    description:
      "Replay actions with a visible virtual hand, e.g. drag a particle to a distance, run the code, or plug a lead into an electrode ({type:'connect', plug, to:{objectId, port}}). Uses the objects' own actions; give an action its own objectId to act on another object.",
    input_schema: {
      type: 'object',
      properties: { objectId: { type: 'string' }, actions: { type: 'array', items: { type: 'object' } } },
      required: ['objectId', 'actions'],
    },
  },
  {
    name: 'highlight',
    description: 'Draw attention to an object or one part of it (e.g. a node id).',
    input_schema: {
      type: 'object',
      properties: { objectId: { type: 'string' }, part: { type: 'string' }, note: { type: 'string' } },
      required: ['objectId'],
    },
  },
]
