/**
 * A tiny Python subset: enough to derive the data-flow graph of short
 * teaching snippets and to evaluate them as a stand-in until Pyodide runs the
 * real thing. Supports top-level assignments, `print(...)`, and one-line
 * functions of the form `def f(a): return <expr>`.
 */

export interface Span {
  start: number
  end: number
}

export type Expr = Span &
  (
    | { k: 'num'; value: number; float: boolean }
    | { k: 'str'; value: string }
    | { k: 'const'; value: null | boolean }
    | { k: 'name'; id: string }
    | { k: 'list'; items: Expr[] }
    | { k: 'comp'; elt: Expr; target: string; iter: Expr; cond: Expr | null }
    | { k: 'call'; fn: string; args: Expr[] }
    | { k: 'unary'; op: '-' | 'not'; arg: Expr }
    | { k: 'bin'; op: string; left: Expr; right: Expr }
    | { k: 'bool'; op: 'and' | 'or'; left: Expr; right: Expr }
    | { k: 'cmp'; op: string; left: Expr; right: Expr }
    | { k: 'ifexp'; test: Expr; body: Expr; orelse: Expr }
  )

export type Stmt =
  | { k: 'assign'; target: string; value: Expr; line: number }
  | { k: 'print'; args: Expr[]; line: number }
  | { k: 'def'; name: string; params: string[]; body: Expr; line: number }

export class PySyntaxError extends Error {}

export class PyError extends Error {
  pyType: string
  constructor(pyType: string, message: string) {
    super(message)
    this.pyType = pyType
  }
}

// ─── Tokenizer ──────────────────────────────────────────────────────────────

type Tok = { t: 'num' | 'str' | 'name' | 'op' | 'end'; v: string; start: number; end: number }

const OPS = ['==', '!=', '<=', '>=', '//', '<', '>', '+', '-', '*', '/', '%', '(', ')', '[', ']', ',', ':', '=']

function tokenize(src: string, base: number): Tok[] {
  const toks: Tok[] = []
  let i = 0
  while (i < src.length) {
    const c = src[i]
    if (c === ' ' || c === '\t') {
      i++
    } else if (c === '#') {
      break
    } else if (/[0-9]/.test(c) || (c === '.' && /[0-9]/.test(src[i + 1] ?? ''))) {
      const m = /^[0-9]*\.?[0-9]*(e[+-]?[0-9]+)?/i.exec(src.slice(i))!
      toks.push({ t: 'num', v: m[0], start: base + i, end: base + i + m[0].length })
      i += m[0].length
    } else if (/[A-Za-z_]/.test(c)) {
      const m = /^[A-Za-z_][A-Za-z0-9_]*/.exec(src.slice(i))!
      toks.push({ t: 'name', v: m[0], start: base + i, end: base + i + m[0].length })
      i += m[0].length
    } else if (c === '"' || c === "'") {
      const close = src.indexOf(c, i + 1)
      if (close < 0) throw new PySyntaxError('unterminated string')
      toks.push({ t: 'str', v: src.slice(i + 1, close), start: base + i, end: base + close + 1 })
      i = close + 1
    } else {
      const op = OPS.find((o) => src.startsWith(o, i))
      if (!op) throw new PySyntaxError(`unexpected character '${c}'`)
      toks.push({ t: 'op', v: op, start: base + i, end: base + i + op.length })
      i += op.length
    }
  }
  toks.push({ t: 'end', v: '', start: base + src.length, end: base + src.length })
  return toks
}

// ─── Parser ─────────────────────────────────────────────────────────────────

const KEYWORDS = new Set(['and', 'or', 'not', 'is', 'in', 'if', 'else', 'for', 'None', 'True', 'False', 'def', 'return'])

class Parser {
  private toks: Tok[]
  private i = 0

  constructor(toks: Tok[]) {
    this.toks = toks
  }

  peek(offset = 0) {
    return this.toks[this.i + offset]
  }
  next() {
    return this.toks[this.i++]
  }
  is(v: string, offset = 0) {
    const t = this.peek(offset)
    return (t.t === 'op' || t.t === 'name') && t.v === v
  }
  eat(v: string) {
    if (!this.is(v)) throw new PySyntaxError(`expected '${v}' but found '${this.peek().v || 'end of line'}'`)
    return this.next()
  }
  done() {
    return this.peek().t === 'end'
  }
  expectEnd() {
    if (!this.done()) throw new PySyntaxError(`unexpected '${this.peek().v}'`)
  }
  name() {
    const t = this.next()
    if (t.t !== 'name' || KEYWORDS.has(t.v)) throw new PySyntaxError(`expected a name but found '${t.v}'`)
    return t.v
  }

  expr(): Expr {
    const body = this.or()
    if (this.is('if') && !this.inComprehensionTail) {
      this.next()
      const test = this.or()
      this.eat('else')
      const orelse = this.expr()
      return { k: 'ifexp', test, body, orelse, start: body.start, end: orelse.end }
    }
    return body
  }

  /** Inside `[elt for x in iter if cond]`, a bare `if` belongs to the comprehension. */
  private inComprehensionTail = false

  or(): Expr {
    let left = this.and()
    while (this.is('or')) {
      this.next()
      const right = this.and()
      left = { k: 'bool', op: 'or', left, right, start: left.start, end: right.end }
    }
    return left
  }
  and(): Expr {
    let left = this.not()
    while (this.is('and')) {
      this.next()
      const right = this.not()
      left = { k: 'bool', op: 'and', left, right, start: left.start, end: right.end }
    }
    return left
  }
  not(): Expr {
    if (this.is('not')) {
      const t = this.next()
      const arg = this.not()
      return { k: 'unary', op: 'not', arg, start: t.start, end: arg.end }
    }
    return this.cmp()
  }
  cmp(): Expr {
    let left = this.sum()
    for (;;) {
      let op: string | null = null
      const t = this.peek()
      if (t.t === 'op' && ['==', '!=', '<', '>', '<=', '>='].includes(t.v)) op = t.v
      else if (this.is('is') && this.is('not', 1)) op = 'is not'
      else if (this.is('is')) op = 'is'
      else if (this.is('not') && this.is('in', 1)) op = 'not in'
      else if (this.is('in') && !this.inComprehensionTail) op = 'in'
      if (!op) return left
      this.i += op.includes(' ') ? 2 : 1
      const right = this.sum()
      left = { k: 'cmp', op, left, right, start: left.start, end: right.end }
    }
  }
  sum(): Expr {
    let left = this.term()
    while (this.is('+') || this.is('-')) {
      const op = this.next().v
      const right = this.term()
      left = { k: 'bin', op, left, right, start: left.start, end: right.end }
    }
    return left
  }
  term(): Expr {
    let left = this.unary()
    while (this.is('*') || this.is('/') || this.is('//') || this.is('%')) {
      const op = this.next().v
      const right = this.unary()
      left = { k: 'bin', op, left, right, start: left.start, end: right.end }
    }
    return left
  }
  unary(): Expr {
    if (this.is('-')) {
      const t = this.next()
      const arg = this.unary()
      return { k: 'unary', op: '-', arg, start: t.start, end: arg.end }
    }
    return this.atom()
  }
  atom(): Expr {
    const t = this.next()
    if (t.t === 'num') {
      const float = /[.e]/i.test(t.v)
      return { k: 'num', value: Number(t.v), float, start: t.start, end: t.end }
    }
    if (t.t === 'str') return { k: 'str', value: t.v, start: t.start, end: t.end }
    if (t.t === 'name') {
      if (t.v === 'None') return { k: 'const', value: null, start: t.start, end: t.end }
      if (t.v === 'True' || t.v === 'False') return { k: 'const', value: t.v === 'True', start: t.start, end: t.end }
      if (KEYWORDS.has(t.v)) throw new PySyntaxError(`unexpected '${t.v}'`)
      if (this.is('(')) {
        this.next()
        const args: Expr[] = []
        while (!this.is(')')) {
          args.push(this.expr())
          if (!this.is(')')) this.eat(',')
        }
        const close = this.eat(')')
        return { k: 'call', fn: t.v, args, start: t.start, end: close.end }
      }
      return { k: 'name', id: t.v, start: t.start, end: t.end }
    }
    if (t.v === '(') {
      const e = this.expr()
      this.eat(')')
      return e
    }
    if (t.v === '[') {
      if (this.is(']')) return { k: 'list', items: [], start: t.start, end: this.next().end }
      const saved = this.inComprehensionTail
      this.inComprehensionTail = true
      const first = this.or()
      if (this.is('for')) {
        this.next()
        const target = this.name()
        this.eat('in')
        const iter = this.or()
        let cond: Expr | null = null
        if (this.is('if')) {
          this.next()
          this.inComprehensionTail = false
          cond = this.expr()
        }
        this.inComprehensionTail = saved
        const close = this.eat(']')
        return { k: 'comp', elt: first, target, iter, cond, start: t.start, end: close.end }
      }
      this.inComprehensionTail = false
      const items = [first]
      while (this.is(',')) {
        this.next()
        if (this.is(']')) break
        items.push(this.expr())
      }
      this.inComprehensionTail = saved
      const close = this.eat(']')
      return { k: 'list', items, start: t.start, end: close.end }
    }
    throw new PySyntaxError(`unexpected '${t.v || 'end of line'}'`)
  }
}

/** Parse a standalone expression, e.g. a condition the student typed. */
export function parseExpr(src: string): Expr {
  const p = new Parser(tokenize(src, 0))
  const e = p.expr()
  p.expectEnd()
  return e
}

/** Parse a whole snippet. Offsets in spans are offsets into `source`. */
export function parseProgram(source: string): Stmt[] {
  const stmts: Stmt[] = []
  const lines = source.split('\n')
  let offset = 0
  let pendingDef: { name: string; params: string[]; line: number } | null = null
  lines.forEach((text, idx) => {
    const base = offset
    offset += text.length + 1
    const line = idx + 1
    const trimmed = text.trim()
    if (!trimmed || trimmed.startsWith('#')) return
    const indent = text.length - text.trimStart().length
    try {
      const p = new Parser(tokenize(text, base))
      if (indent > 0) {
        if (!pendingDef || !p.is('return')) throw new PySyntaxError('only `return <expr>` is supported inside a function')
        p.next()
        const body = p.expr()
        p.expectEnd()
        stmts.push({ k: 'def', ...pendingDef, body })
        pendingDef = null
        return
      }
      if (pendingDef) throw new PySyntaxError(`function '${pendingDef.name}' has no body`)
      if (p.is('def')) {
        p.next()
        const name = p.name()
        p.eat('(')
        const params: string[] = []
        while (!p.is(')')) {
          params.push(p.name())
          if (!p.is(')')) p.eat(',')
        }
        p.eat(')')
        p.eat(':')
        p.expectEnd()
        pendingDef = { name, params, line }
        return
      }
      if (p.is('print') && p.is('(', 1)) {
        const call = p.expr()
        p.expectEnd()
        if (call.k !== 'call') throw new PySyntaxError('bad print')
        stmts.push({ k: 'print', args: call.args, line })
        return
      }
      const target = p.name()
      p.eat('=')
      const value = p.expr()
      p.expectEnd()
      stmts.push({ k: 'assign', target, value, line })
    } catch (e) {
      if (e instanceof PySyntaxError) throw new PySyntaxError(`line ${line}: ${e.message}`)
      throw e
    }
  })
  if (pendingDef) throw new PySyntaxError(`function has no body`)
  return stmts
}

/** Names an expression reads, excluding comprehension variables. */
export function namesIn(e: Expr, bound: Set<string> = new Set()): Set<string> {
  const out = new Set<string>()
  const walk = (x: Expr, b: Set<string>) => {
    switch (x.k) {
      case 'name':
        if (!b.has(x.id)) out.add(x.id)
        break
      case 'list':
        x.items.forEach((i) => walk(i, b))
        break
      case 'comp': {
        walk(x.iter, b)
        const inner = new Set(b).add(x.target)
        walk(x.elt, inner)
        if (x.cond) walk(x.cond, inner)
        break
      }
      case 'call':
        x.args.forEach((a) => walk(a, b))
        break
      case 'unary':
        walk(x.arg, b)
        break
      case 'bin':
      case 'bool':
      case 'cmp':
        walk(x.left, b)
        walk(x.right, b)
        break
      case 'ifexp':
        walk(x.test, b)
        walk(x.body, b)
        walk(x.orelse, b)
        break
    }
  }
  walk(e, bound)
  return out
}

// ─── Values and evaluation ─────────────────────────────────────────────────

export interface PyFloat {
  float: number
}
export type PyValue = null | boolean | number | string | PyFloat | PyValue[]

const isFloat = (v: PyValue): v is PyFloat => typeof v === 'object' && v !== null && !Array.isArray(v)
const isNum = (v: PyValue) => (typeof v === 'number' || typeof v === 'boolean' || isFloat(v)) && v !== null
const num = (v: PyValue) => (isFloat(v) ? v.float : Number(v))

export function typeName(v: PyValue): string {
  if (v === null) return 'NoneType'
  if (typeof v === 'boolean') return 'bool'
  if (typeof v === 'number') return 'int'
  if (typeof v === 'string') return 'str'
  if (Array.isArray(v)) return 'list'
  return 'float'
}

export function truthy(v: PyValue): boolean {
  if (v === null) return false
  if (Array.isArray(v)) return v.length > 0
  if (isFloat(v)) return v.float !== 0
  return Boolean(v)
}

export function repr(v: PyValue): string {
  if (v === null) return 'None'
  if (v === true) return 'True'
  if (v === false) return 'False'
  if (typeof v === 'number') return String(v)
  if (typeof v === 'string') return `'${v}'`
  if (Array.isArray(v)) return `[${v.map(repr).join(', ')}]`
  return Number.isInteger(v.float) ? `${v.float}.0` : String(v.float)
}

export const str = (v: PyValue) => (typeof v === 'string' ? v : repr(v))

function arith(op: string, a: PyValue, b: PyValue): PyValue {
  if (op === '+' && Array.isArray(a) && Array.isArray(b)) return [...a, ...b]
  if (op === '+' && typeof a === 'string' && typeof b === 'string') return a + b
  if (!isNum(a) || !isNum(b))
    throw new PyError('TypeError', `unsupported operand type(s) for ${op}: '${typeName(a)}' and '${typeName(b)}'`)
  const x = num(a)
  const y = num(b)
  const float = isFloat(a) || isFloat(b)
  const wrap = (r: number) => (float ? { float: r } : r)
  switch (op) {
    case '+':
      return wrap(x + y)
    case '-':
      return wrap(x - y)
    case '*':
      return wrap(x * y)
    case '/':
      if (y === 0) throw new PyError('ZeroDivisionError', 'division by zero')
      return { float: x / y }
    case '//':
      if (y === 0) throw new PyError('ZeroDivisionError', 'integer division or modulo by zero')
      return wrap(Math.floor(x / y))
    case '%':
      if (y === 0) throw new PyError('ZeroDivisionError', 'integer modulo by zero')
      return wrap(((x % y) + y) % y)
  }
  throw new PyError('SyntaxError', `unknown operator ${op}`)
}

function equal(a: PyValue, b: PyValue): boolean {
  if (isNum(a) && isNum(b)) return num(a) === num(b)
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((x, i) => equal(x, b[i]))
  return a === b
}

function compare(op: string, a: PyValue, b: PyValue): boolean {
  switch (op) {
    case '==':
      return equal(a, b)
    case '!=':
      return !equal(a, b)
    case 'is':
      return a === b || (a === null && b === null)
    case 'is not':
      return !(a === b || (a === null && b === null))
    case 'in':
    case 'not in': {
      if (!Array.isArray(b)) throw new PyError('TypeError', `argument of type '${typeName(b)}' is not iterable`)
      const found = b.some((x) => equal(x, a))
      return op === 'in' ? found : !found
    }
  }
  const comparable = (isNum(a) && isNum(b)) || (typeof a === 'string' && typeof b === 'string')
  if (!comparable)
    throw new PyError('TypeError', `'${op}' not supported between instances of '${typeName(a)}' and '${typeName(b)}'`)
  const x = typeof a === 'string' ? a : num(a)
  const y = typeof b === 'string' ? b : num(b)
  return op === '<' ? x < y : op === '>' ? x > y : op === '<=' ? x <= y : x >= y
}

export type Env = Map<string, PyValue>
export type Funcs = Map<string, { params: string[]; body: Expr }>

/** Called for each item a comprehension looks at, so callers can trace filters. */
export type IterHook = (comp: Expr, item: PyValue, kept: boolean | 'error') => void

export function evalExpr(e: Expr, env: Env, funcs: Funcs = new Map(), hook?: IterHook): PyValue {
  const ev = (x: Expr, en: Env = env) => evalExpr(x, en, funcs, hook)
  switch (e.k) {
    case 'num':
      return e.float ? { float: e.value } : e.value
    case 'str':
      return e.value
    case 'const':
      return e.value
    case 'name':
      if (!env.has(e.id)) throw new PyError('NameError', `name '${e.id}' is not defined`)
      return env.get(e.id)!
    case 'list':
      return e.items.map((i) => ev(i))
    case 'comp': {
      const iter = ev(e.iter)
      if (!Array.isArray(iter)) throw new PyError('TypeError', `'${typeName(iter)}' object is not iterable`)
      const out: PyValue[] = []
      for (const item of iter) {
        const inner = new Map(env).set(e.target, item)
        let keep = true
        try {
          if (e.cond) keep = truthy(ev(e.cond, inner))
        } catch (err) {
          hook?.(e, item, 'error')
          throw err
        }
        hook?.(e, item, keep)
        if (keep) out.push(ev(e.elt, inner))
      }
      return out
    }
    case 'call': {
      const args = e.args.map((a) => ev(a))
      const fn = funcs.get(e.fn)
      if (fn) {
        const local = new Map(env)
        fn.params.forEach((p, i) => local.set(p, args[i] ?? null))
        return evalExpr(fn.body, local, funcs, hook)
      }
      return builtin(e.fn, args)
    }
    case 'unary':
      if (e.op === 'not') return !truthy(ev(e.arg))
      return arith('-', 0, ev(e.arg))
    case 'bin':
      return arith(e.op, ev(e.left), ev(e.right))
    case 'bool': {
      const left = ev(e.left)
      if (e.op === 'and') return truthy(left) ? ev(e.right) : left
      return truthy(left) ? left : ev(e.right)
    }
    case 'cmp':
      return compare(e.op, ev(e.left), ev(e.right))
    case 'ifexp':
      return truthy(ev(e.test)) ? ev(e.body) : ev(e.orelse)
  }
}

function builtin(name: string, args: PyValue[]): PyValue {
  const [a] = args
  switch (name) {
    case 'len':
      if (!Array.isArray(a) && typeof a !== 'string') throw new PyError('TypeError', `object of type '${typeName(a)}' has no len()`)
      return a.length
    case 'sum':
      if (!Array.isArray(a)) throw new PyError('TypeError', `'${typeName(a)}' object is not iterable`)
      return a.reduce<PyValue>((acc, x) => arith('+', acc, x), 0)
    case 'bool':
      return truthy(a)
    case 'abs':
      return arith('*', a, num(a) < 0 ? -1 : 1)
    case 'min':
    case 'max': {
      const items = args.length === 1 && Array.isArray(a) ? a : args
      if (!items.length) throw new PyError('ValueError', `${name}() arg is an empty sequence`)
      return items.reduce((m, x) => (compare(name === 'min' ? '<' : '>', x, m) ? x : m))
    }
  }
  throw new PyError('NameError', `name '${name}' is not defined`)
}

/** Parse a literal the student drags in, e.g. `0`, `None`, `-5`. */
export function literal(src: string): PyValue {
  return evalExpr(parseExpr(src), new Map())
}
