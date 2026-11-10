import { useEffect, useMemo, useState, type PointerEvent } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../core/cn'
import type { ObjectViewProps } from '../types'
import type { GraphNode } from './graph'
import type { CodeGraphState, ProbeResult } from './module'
import { parseExpr } from './python'

const NODE_W = 132
const NODE_H = 92
const GAP_X = 52
const GAP_Y = 24
const PAD = 12
const STEP_MS = 420

const KIND_LABEL: Record<GraphNode['kind'], string> = {
  input: 'input',
  filter: 'filter',
  call: 'compute',
  expr: 'expression',
}

function layout(nodes: GraphNode[]) {
  const byLayer = new Map<number, GraphNode[]>()
  nodes.forEach((n) => byLayer.set(n.layer, [...(byLayer.get(n.layer) ?? []), n]))
  const rows = Math.max(1, ...[...byLayer.values()].map((l) => l.length))
  // Extra room below for the chips under the filter node.
  const height = rows * NODE_H + (rows - 1) * GAP_Y + PAD * 2 + 56
  const pos = new Map<string, { x: number; y: number }>()
  byLayer.forEach((list, layer) => {
    const colH = list.length * NODE_H + (list.length - 1) * GAP_Y
    list.forEach((n, i) => {
      pos.set(n.id, { x: PAD + layer * (NODE_W + GAP_X), y: (height - 56 - colH) / 2 + i * (NODE_H + GAP_Y) })
    })
  })
  const layers = Math.max(1, ...nodes.map((n) => n.layer + 1))
  return { pos, width: PAD * 2 + layers * NODE_W + (layers - 1) * GAP_X, height }
}

/** Replays a run's trace step by step. Returns how many steps are visible. */
function usePlayhead(runId: number | undefined, steps: number) {
  const [anim, setAnim] = useState({ runId: -1, step: 0 })
  const step = anim.runId === runId ? anim.step : 0
  useEffect(() => {
    if (runId === undefined) return
    let k = 0
    const timer = setInterval(() => {
      k += 1
      setAnim({ runId, step: k })
      if (k >= steps) clearInterval(timer)
    }, STEP_MS)
    return () => clearInterval(timer)
  }, [runId, steps])
  return step
}

export function CodeGraphView({ object, state, dispatch, demonstrating, highlight }: ObjectViewProps<'code-graph', CodeGraphState>) {
  const { graph, lastRun, previousRun } = state
  const { pos, width, height } = useMemo(() => layout(graph?.nodes ?? []), [graph])
  const trace = lastRun?.trace ?? []
  const step = usePlayhead(lastRun?.runId, trace.length)
  const playing = !!lastRun && step < trace.length

  // What the replay has revealed so far.
  const shown = trace.slice(0, step)
  const current = playing ? trace[step] : null
  const values = new Map<string, string>()
  const errors = new Map<string, string>()
  shown.forEach((t) => {
    if (t.kind === 'assign') values.set(t.nodeId, t.value)
    if (t.kind === 'error') errors.set(t.nodeId, t.message)
  })
  const iterations = shown.filter((t) => t.kind === 'iterate')
  const [drag, setDrag] = useState<{ value: string; x: number; y: number; over: string | null } | null>(null)

  const filterLine = useMemo(() => {
    const f = graph?.nodes.find((n) => n.filter)?.filter
    return f ? state.source.slice(0, f.span.start).split('\n').length : null
  }, [graph, state.source])

  if (!graph) {
    return <p className="p-4 text-sm text-bad">Can't parse the source: {state.parseError}</p>
  }

  return (
    <div className="flex flex-col gap-3 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          data-anchor={`${object.id}/run`}
          disabled={state.running || demonstrating}
          onClick={() => dispatch({ type: 'run' })}
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:opacity-90 disabled:opacity-50"
        >
          {state.running ? 'Running…' : '▶ Run'}
        </button>
        {lastRun && <RunTag provenance={lastRun.provenance} />}
        {state.stale && <span className="rounded bg-warn/15 px-2 py-0.5 text-xs text-warn">Source changed since the last run</span>}
        <span className="ml-auto text-xs text-muted">Graph derived from the source</span>
      </div>

      <div className="relative overflow-x-auto rounded-lg border border-line bg-bg" style={{ height }}>
        <svg className="absolute inset-0" width={width} height={height}>
          <defs>
            <marker id={`arrow-${object.id}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" className="fill-muted" />
            </marker>
          </defs>
          {graph.edges.map((e) => {
            const a = pos.get(e.from)!
            const b = pos.get(e.to)!
            const x1 = a.x + NODE_W
            const y1 = a.y + NODE_H / 2
            const x2 = b.x - 2
            const y2 = b.y + NODE_H / 2
            const active = current?.nodeId === e.to
            return (
              <path
                key={`${e.from}-${e.to}`}
                d={`M${x1},${y1} C${x1 + GAP_X / 2},${y1} ${x2 - GAP_X / 2},${y2} ${x2},${y2}`}
                className={cn('fill-none transition-colors', active ? 'stroke-accent' : 'stroke-line')}
                strokeWidth={active ? 2.5 : 1.5}
                markerEnd={`url(#arrow-${object.id})`}
              />
            )
          })}
        </svg>
        {graph.nodes.map((n) => (
          <Node
            key={n.id}
            objectId={object.id}
            node={n}
            at={pos.get(n.id)!}
            value={values.get(n.id)}
            previous={previousRun?.values[n.id]}
            error={errors.get(n.id)}
            active={current?.nodeId === n.id}
            highlighted={highlight?.part === n.id}
            probes={state.probes[n.id] ?? []}
            iterations={n.filter ? iterations.filter((t) => t.nodeId === n.id) : []}
            liveIteration={current?.kind === 'iterate' && current.nodeId === n.id ? current : null}
            playing={playing}
            dropping={drag?.over === n.id}
            onEdit={(condition) => dispatch({ type: 'editCondition', nodeId: n.id, condition })}
          />
        ))}
      </div>

      <ProbeTray
        values={object.config.probeValues}
        disabled={demonstrating}
        onDrag={setDrag}
        onDrop={(value, nodeId) => dispatch({ type: 'probe', nodeId, value })}
      />
      {drag &&
        createPortal(
          <span
            className="pointer-events-none fixed z-50 -translate-x-1/2 -translate-y-1/2 rounded-full border border-accent bg-accent px-2.5 py-0.5 font-mono text-xs text-white shadow-lg"
            style={{ left: drag.x, top: drag.y }}
          >
            {drag.value}
          </span>,
          document.body,
        )}

      <details className="group rounded-lg border border-line" open>
        <summary className="cursor-pointer select-none px-3 py-1.5 text-xs text-muted">Source (the single source of truth)</summary>
        <pre className="overflow-x-auto border-t border-line px-3 py-2 font-mono text-[12px] leading-5">
          {state.source.split('\n').map((line, i) => (
            <div key={i} className={cn('flex gap-3', i + 1 === filterLine && 'bg-accent-soft')}>
              <span className="w-5 shrink-0 text-right text-muted/60 select-none">{i + 1}</span>
              <span className={cn(line.trim().startsWith('#') && 'text-muted')}>{line || ' '}</span>
            </div>
          ))}
        </pre>
      </details>

      {lastRun && !playing && (
        <details className="rounded-lg border border-line">
          <summary className="cursor-pointer select-none px-3 py-1.5 text-xs text-muted">Output (stdout)</summary>
          <pre className="overflow-x-auto border-t border-line px-3 py-2 font-mono text-[12px] leading-5 whitespace-pre-wrap">
            {lastRun.stdout || '(no output)'}
          </pre>
        </details>
      )}
    </div>
  )
}

function RunTag({ provenance }: { provenance: 'real-run' | 'simulated' }) {
  return provenance === 'real-run' ? (
    <span className="rounded bg-good/15 px-2 py-0.5 text-xs font-medium text-good">Real run · Pyodide</span>
  ) : (
    <span className="rounded bg-warn/15 px-2 py-0.5 text-xs font-medium text-warn">Simulated · JS interpreter</span>
  )
}

type NodeProps = {
  objectId: string
  node: GraphNode
  at: { x: number; y: number }
  value?: string
  previous?: string
  error?: string
  active: boolean
  highlighted: boolean
  probes: ProbeResult[]
  iterations: { value: string; kept: boolean | 'error' }[]
  liveIteration: { value: string; kept: boolean | 'error' } | null
  playing: boolean
  dropping: boolean
  onEdit: (condition: string) => void
}

function Node({ objectId, node, at, value, previous, error, active, highlighted, probes, iterations, liveIteration, playing, dropping, onEdit }: NodeProps) {
  const isFilter = !!node.filter
  // While a run replays, show its iterations; otherwise the student's probes (or the last run's).
  const chips = playing ? [...iterations, ...(liveIteration ? [liveIteration] : [])] : probes.length ? probes : iterations
  return (
    <div
      data-anchor={`${objectId}/node:${node.id}`}
      className={cn(
        'absolute flex flex-col rounded-lg border bg-surface px-2 py-1.5 shadow-sm transition-all',
        isFilter ? 'border-accent/60' : 'border-line',
        active && 'ring-2 ring-accent',
        highlighted && 'ring-4 ring-warn/70',
        dropping && 'scale-105 ring-2 ring-accent',
        error && 'border-bad ring-2 ring-bad/40',
      )}
      style={{ left: at.x, top: at.y, width: NODE_W, height: NODE_H }}
      data-probe-target={isFilter ? node.id : undefined}
    >
      <div className="flex items-center gap-1.5">
        <span className={cn('rounded px-1 text-[10px] font-medium', isFilter ? 'bg-accent text-white' : 'bg-line text-muted')}>
          {KIND_LABEL[node.kind]}
        </span>
        <span className="truncate font-mono text-xs font-semibold">{node.id}</span>
      </div>
      {isFilter ? (
        <ConditionEditor loopVar={node.filter!.loopVar} condition={node.filter!.condition} onCommit={onEdit} />
      ) : (
        <code className="mt-1 truncate font-mono text-[11px] text-muted" title={node.code}>
          {node.code}
        </code>
      )}
      <div className="mt-auto truncate font-mono text-[11px]">
        {error ? (
          <span className="text-bad" title={error}>
            {error}
          </span>
        ) : value !== undefined ? (
          <span>
            {previous !== undefined && previous !== value && <span className="mr-1 text-muted line-through">{previous}</span>}
            <span className="font-semibold text-accent">= {value}</span>
          </span>
        ) : isFilter ? (
          <span className="text-muted/70">Drop a test value here</span>
        ) : null}
      </div>

      {isFilter && chips.length > 0 && (
        <div className="absolute top-full left-0 mt-1.5 flex flex-wrap gap-1" style={{ width: NODE_W + GAP_X - 8 }}>
          {chips.map((p, i) => (
            <KeptChip key={`${p.value}-${i}`} value={p.value} kept={p.kept} live={p === liveIteration} />
          ))}
        </div>
      )}
    </div>
  )
}

function KeptChip({ value, kept, live }: { value: string; kept: boolean | 'error'; live?: boolean }) {
  return (
    <span
      className={cn(
        'rounded-full border px-1.5 py-0.5 font-mono text-[10px] transition-transform',
        kept === true && 'border-good/40 bg-good/10 text-good',
        kept === false && 'border-bad/40 bg-bad/10 text-bad line-through',
        kept === 'error' && 'border-bad bg-bad text-white',
        live && 'scale-125',
      )}
    >
      {value} {kept === true ? 'kept' : kept === false ? 'dropped' : 'error'}
    </span>
  )
}

function ConditionEditor({ loopVar, condition, onCommit }: { loopVar: string; condition: string; onCommit: (c: string) => void }) {
  const [draft, setDraft] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  if (draft === null) {
    return (
      <button
        type="button"
        title="Click to edit the condition"
        onClick={() => setDraft(condition)}
        className="mt-1 w-full truncate rounded border border-dashed border-accent/40 px-1 text-left font-mono text-[11px] hover:bg-accent-soft"
      >
        <span className="text-muted">if </span>
        {condition}
        <span className="sr-only">(click to edit; {loopVar} is the current item)</span>
      </button>
    )
  }
  const commit = () => {
    try {
      parseExpr(draft)
      setDraft(null)
      setError(null)
      if (draft.trim() !== condition) onCommit(draft.trim())
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }
  return (
    <div className="mt-1">
      <input
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit()
          if (e.key === 'Escape') {
            setDraft(null)
            setError(null)
          }
        }}
        onBlur={commit}
        className={cn('w-full rounded border bg-surface px-1 font-mono text-[11px] outline-none', error ? 'border-bad' : 'border-accent')}
      />
      {error && <p className="absolute z-10 mt-0.5 rounded bg-bad px-1 text-[10px] text-white">{error}</p>}
    </div>
  )
}

type Drag = { value: string; x: number; y: number; over: string | null }

/** Test values the student drags onto a filter node (pointer-based, so it works with touch too). */
function ProbeTray({
  values,
  disabled,
  onDrag,
  onDrop,
}: {
  values: string[]
  disabled: boolean
  onDrag: (d: Drag | null) => void
  onDrop: (value: string, nodeId: string) => void
}) {
  if (!values.length) return null
  const targetAt = (x: number, y: number) =>
    (document.elementFromPoint(x, y)?.closest('[data-probe-target]') as HTMLElement | null)?.dataset.probeTarget ?? null
  const handlers = (value: string) => ({
    onPointerDown: (e: PointerEvent) => {
      if (disabled) return
      e.currentTarget.setPointerCapture(e.pointerId)
      onDrag({ value, x: e.clientX, y: e.clientY, over: null })
    },
    onPointerMove: (e: PointerEvent) => {
      if (!e.currentTarget.hasPointerCapture(e.pointerId)) return
      onDrag({ value, x: e.clientX, y: e.clientY, over: targetAt(e.clientX, e.clientY) })
    },
    onPointerUp: (e: PointerEvent) => {
      if (!e.currentTarget.hasPointerCapture(e.pointerId)) return
      const target = targetAt(e.clientX, e.clientY)
      onDrag(null)
      if (target) onDrop(value, target)
    },
    onPointerCancel: () => onDrag(null),
  })
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
      <span>Drag a test value onto the filter node:</span>
      {values.map((v) => (
        <span
          key={v}
          data-probe-value={v}
          {...handlers(v)}
          className="cursor-grab touch-none rounded-full border border-accent/50 bg-accent-soft px-2.5 py-0.5 font-mono text-xs text-accent shadow-sm active:cursor-grabbing"
        >
          {v}
        </span>
      ))}
    </div>
  )
}
