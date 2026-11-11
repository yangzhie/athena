import { namesIn, parseExpr, parseProgram, type Expr, type Span, type Stmt } from './python'

export type GraphNodeKind = 'input' | 'filter' | 'call' | 'expr'

export interface GraphNode {
  id: string // the name the source assigns
  kind: GraphNodeKind
  /** Short code shown on the node, e.g. `sum(cleaned)`. */
  code: string
  deps: string[]
  line: number
  layer: number
  /** Filter nodes only: the condition, its loop variable and where it sits in the source. */
  filter?: { condition: string; loopVar: string; span: Span }
}

export interface CodeGraph {
  nodes: GraphNode[]
  edges: { from: string; to: string }[]
  layers: number
}

/** Find the comprehension a node filters with, following one call into a user function. */
function findComprehension(value: Expr, defs: Map<string, Extract<Stmt, { k: 'def' }>>) {
  if (value.k === 'comp' && value.cond) return value
  if (value.k === 'call') {
    const def = defs.get(value.fn)
    if (def?.body.k === 'comp' && def.body.cond) return def.body
  }
  return null
}

/** Derive the data-flow graph from source. The source stays the only truth. */
export function deriveGraph(source: string): CodeGraph {
  const stmts = parseProgram(source)
  const defs = new Map(stmts.filter((s) => s.k === 'def').map((s) => [s.name, s]))
  const nodes: GraphNode[] = []
  const byId = new Map<string, GraphNode>()
  for (const s of stmts) {
    if (s.k !== 'assign') continue
    const deps = [...namesIn(s.value)].filter((n) => byId.has(n))
    const comp = findComprehension(s.value, defs)
    const code = source.slice(s.value.start, s.value.end)
    let kind: GraphNodeKind = 'expr'
    if (comp?.cond) kind = 'filter'
    else if (!deps.length) kind = 'input'
    else if (s.value.k === 'call') kind = 'call'
    const layer = deps.length ? Math.max(...deps.map((d) => byId.get(d)!.layer)) + 1 : 0
    const node: GraphNode = { id: s.target, kind, code, deps, line: s.line, layer }
    if (comp?.cond) {
      node.filter = {
        condition: source.slice(comp.cond.start, comp.cond.end),
        loopVar: comp.target,
        span: { start: comp.cond.start, end: comp.cond.end },
      }
    }
    nodes.push(node)
    byId.set(node.id, node)
  }
  const edges = nodes.flatMap((n) => n.deps.map((d) => ({ from: d, to: n.id })))
  return { nodes, edges, layers: Math.max(0, ...nodes.map((n) => n.layer)) + 1 }
}

/** Rewrite one filter node's condition in the source. Throws on invalid conditions. */
export function replaceCondition(source: string, graph: CodeGraph, nodeId: string, condition: string): string {
  const node = graph.nodes.find((n) => n.id === nodeId)
  if (!node?.filter) throw new Error(`'${nodeId}' is not a filter node`)
  parseExpr(condition)
  const { start, end } = node.filter.span
  return source.slice(0, start) + condition.trim() + source.slice(end)
}

/** The changed lines between two versions of a snippet, for a diff preview. */
export function lineDiff(before: string, after: string) {
  const a = before.split('\n')
  const b = after.split('\n')
  const changed: { line: number; before: string; after: string }[] = []
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if (a[i] !== b[i]) changed.push({ line: i + 1, before: a[i] ?? '', after: b[i] ?? '' })
  }
  return changed
}
