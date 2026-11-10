import type { CodeGraphConfig, Observation, RunResult } from '../../contracts'
import { defineModule } from '../types'
import { CodeGraphView } from './CodeGraphView'
import { deriveGraph, lineDiff, replaceCondition, type CodeGraph } from './graph'
import { evalExpr, literal, parseExpr, PyError, truthy } from './python'
import { s } from '../../core/schema'

export interface ProbeResult {
  value: string
  kept: boolean | 'error'
  message?: string
}

export interface CodeGraphState {
  source: string
  graph: CodeGraph | null
  parseError: string | null
  /** Latest probe results per filter node, newest last. */
  probes: Record<string, ProbeResult[]>
  runId: number
  running: boolean
  lastRun: (RunResult & { runId: number; source: string }) | null
  /** The run before `lastRun`, kept for before/after comparison. */
  previousRun: (RunResult & { runId: number; source: string }) | null
  /** The source changed after `lastRun`. */
  stale: boolean
}

function derive(source: string): Pick<CodeGraphState, 'graph' | 'parseError'> {
  try {
    return { graph: deriveGraph(source), parseError: null }
  } catch (e) {
    return { graph: null, parseError: e instanceof Error ? e.message : String(e) }
  }
}

/** Evaluate one filter node's condition for a single value, as Python would. */
export function probe(graph: CodeGraph, nodeId: string, value: string): ProbeResult {
  const node = graph.nodes.find((n) => n.id === nodeId)
  if (!node?.filter) return { value, kept: 'error', message: `'${nodeId}' is not a filter` }
  try {
    const env = new Map([[node.filter.loopVar, literal(value)]])
    return { value, kept: truthy(evalExpr(parseExpr(node.filter.condition), env)) }
  } catch (e) {
    const message = e instanceof PyError ? `${e.pyType}: ${e.message}` : String(e)
    return { value, kept: 'error', message }
  }
}

function pushProbe(list: ProbeResult[] = [], r: ProbeResult) {
  return [...list.filter((p) => p.value !== r.value), r].slice(-4)
}

const filterNode = (s: CodeGraphState, nodeId: string) => s.graph?.nodes.find((n) => n.id === nodeId && n.filter)

export const codeGraphModule = defineModule<'code-graph', CodeGraphState>({
  type: 'code-graph',
  label: 'Code graph',
  about: {
    summary:
      'Python source shown as a data-flow graph derived from it (the source stays the truth). The student drags test values onto filter nodes, edits a filter condition, and runs the code. Supports a small Python subset: assignments, list literals, list comprehensions with `if`, def/return, sum/len/print, arithmetic and comparisons, `is (not) None`.',
    config: s.object({
      language: s.string('Always "python"', ['python']),
      source: s.string('The program; node ids are the names it assigns'),
      probeValues: s.array(s.string('A Python literal, e.g. "0" or "None"'), 'Values the student can drag onto a filter node', 1, 6),
    }),
    actions: {
      probe: '{nodeId, value}: test one value against a filter node',
      editCondition: '{nodeId, condition}: replace a filter condition (prefer the edit_node tool, which asks the student first)',
      run: '{}: run the program and replay its trace',
    },
    observes: {
      on: ['probe', 'editCondition', 'runCompleted'],
      fields: {
        node: 'filter node id',
        value: 'probe: the value tried (Python literal)',
        kept: 'probe: true, false or "error"',
        condition: 'the filter condition',
        'keeps.*': 'editCondition: for each probe value, whether the new condition keeps it (true/false/"error")',
        ok: 'runCompleted: the run finished without an error',
        error: 'runCompleted: the Python exception type, or null',
        'value.*': 'runCompleted: final value of a top-level name, as a Python repr (e.g. "10.0")',
      },
    },
  },
  width: 760,
  init: (config: CodeGraphConfig) => ({
    source: config.source,
    ...derive(config.source),
    probes: {},
    runId: 0,
    running: false,
    lastRun: null,
    previousRun: null,
    stale: false,
  }),
  edits: ['editCondition'],
  reduce(state, action) {
    switch (action.type) {
      case 'probe': {
        if (!state.graph || !filterNode(state, action.nodeId)) return state
        const r = probe(state.graph, action.nodeId, action.value)
        return { ...state, probes: { ...state.probes, [action.nodeId]: pushProbe(state.probes[action.nodeId], r) } }
      }
      case 'editCondition': {
        if (!state.graph) return state
        let source: string
        try {
          source = replaceCondition(state.source, state.graph, action.nodeId, action.condition)
        } catch {
          return state
        }
        const next = { ...state, source, ...derive(source), stale: state.lastRun !== null }
        // Re-evaluate the probes the student already tried against the new condition.
        const probes = Object.fromEntries(
          Object.entries(state.probes).map(([id, list]) => [id, next.graph ? list.map((p) => probe(next.graph!, id, p.value)) : []]),
        )
        return { ...next, probes }
      }
      case 'run':
        return { ...state, runId: state.runId + 1, running: true }
      case 'runCompleted': {
        if (action.runId !== state.runId) return state
        const run = { ...action.result, runId: action.runId, source: state.source }
        const changed = state.lastRun && state.lastRun.source !== state.source
        return {
          ...state,
          running: false,
          stale: false,
          lastRun: run,
          previousRun: changed ? state.lastRun : state.previousRun,
        }
      }
    }
    return state
  },
  observe(state, action, config) {
    switch (action.type) {
      case 'probe': {
        const r = state.probes[action.nodeId]?.find((p) => p.value === action.value)
        if (!r) return null
        return { action: 'probe', node: action.nodeId, value: action.value, kept: r.kept, condition: filterNode(state, action.nodeId)?.filter?.condition ?? null }
      }
      case 'editCondition': {
        if (!state.graph) return null
        const obs: Observation = { action: 'editCondition', node: action.nodeId, condition: action.condition }
        for (const v of config.probeValues) obs[`keeps.${v}`] = probe(state.graph, action.nodeId, v).kept
        return obs
      }
      case 'runCompleted': {
        if (!state.lastRun || action.runId !== state.lastRun.runId) return null
        const obs: Observation = { action: 'runCompleted', ok: state.lastRun.ok, error: state.lastRun.error?.type ?? null }
        for (const [k, v] of Object.entries(state.lastRun.values)) obs[`value.${k}`] = v
        return obs
      }
    }
    return null
  },
  async effect(state, action, { runtimes, dispatch }) {
    if (action.type !== 'run') return
    const runId = state.runId
    const result = await runtimes.python.run(state.source)
    dispatch({ type: 'runCompleted', runId, result })
  },
  anchor(action) {
    if (action.type === 'run') return 'run'
    if (action.type === 'probe' || action.type === 'editCondition') return `node:${action.nodeId}`
    return 'body'
  },
  validate(state, action) {
    if (action.type !== 'editCondition') return null
    if (!state.graph) return 'the source does not parse'
    try {
      replaceCondition(state.source, state.graph, action.nodeId, action.condition)
      return null
    } catch (e) {
      return e instanceof Error ? e.message : String(e)
    }
  },
  preview(state, action) {
    if (action.type !== 'editCondition' || !state.graph) return null
    const after = replaceCondition(state.source, state.graph, action.nodeId, action.condition)
    const changed = lineDiff(state.source, after)
    return { before: changed.map((c) => c.before).join('\n'), after: changed.map((c) => c.after).join('\n') }
  },
  summarize(state) {
    return {
      source: state.source,
      filters: state.graph?.nodes.filter((n) => n.filter).map((n) => ({ node: n.id, condition: n.filter!.condition })),
      probes: state.probes,
      lastRun: state.lastRun && {
        provenance: state.lastRun.provenance,
        ok: state.lastRun.ok,
        values: state.lastRun.values,
        error: state.lastRun.error,
        stale: state.stale,
      },
      previousRunValues: state.previousRun?.values,
    }
  },
  View: CodeGraphView,
})
