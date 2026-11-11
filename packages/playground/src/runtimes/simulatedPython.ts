import type { CodeRuntime, RunResult, TraceStep } from '../contracts'
import { evalExpr, parseProgram, PyError, PySyntaxError, repr, str, type Env, type Funcs } from '../objects/codeGraph/python'

/**
 * Evaluates the supported Python subset in JS. A stand-in until the Pyodide
 * runtime lands; results are labelled `simulated`, never `real-run`.
 */
export const simulatedPython: CodeRuntime = {
  provenance: 'simulated',
  async run(source) {
    const trace: TraceStep[] = []
    const values: Record<string, string> = {}
    let stdout = ''
    const done = (extra: Partial<RunResult> = {}): RunResult => ({
      ok: true,
      provenance: 'simulated',
      stdout,
      values,
      trace,
      ...extra,
    })
    let stmts
    try {
      stmts = parseProgram(source)
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      return done({ ok: false, error: { type: 'SyntaxError', message } })
    }
    const env: Env = new Map()
    const funcs: Funcs = new Map()
    for (const s of stmts) {
      const nodeId = s.k === 'assign' ? s.target : undefined
      try {
        if (s.k === 'def') {
          funcs.set(s.name, { params: s.params, body: s.body })
        } else if (s.k === 'print') {
          stdout += s.args.map((a) => str(evalExpr(a, env, funcs))).join(' ') + '\n'
        } else {
          const value = evalExpr(s.value, env, funcs, (_comp, item, kept) =>
            trace.push({ kind: 'iterate', nodeId: s.target, value: repr(item), kept }),
          )
          env.set(s.target, value)
          values[s.target] = repr(value)
          trace.push({ kind: 'assign', nodeId: s.target, value: repr(value) })
        }
      } catch (e) {
        if (!(e instanceof PyError) && !(e instanceof PySyntaxError)) throw e
        const type = e instanceof PyError ? e.pyType : 'SyntaxError'
        if (nodeId) trace.push({ kind: 'error', nodeId, message: `${type}: ${e.message}` })
        stdout += `Traceback (line ${s.line}):\n${type}: ${e.message}\n`
        return done({ ok: false, error: { type, message: e.message, nodeId } })
      }
    }
    return done()
  },
}
