import assert from 'node:assert/strict'
import { after, before, beforeEach, test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

// Use the host's existing Vite compiler to load the package's TypeScript/TSX.
let server
let Playground
let noteModule
let observers
const originalResizeObserver = globalThis.ResizeObserver

class TestResizeObserver {
  constructor(callback) {
    this.callback = callback
    this.disconnected = false
    observers.push(this)
  }
  observe() {}
  disconnect() {
    this.disconnected = true
  }
  resize() {
    this.callback()
  }
}

before(async () => {
  globalThis.ResizeObserver = TestResizeObserver
  server = await createServer({
    root: fileURLToPath(new URL('../../../packages/playground/', import.meta.url)),
    configFile: false,
    server: { middlewareMode: true, hmr: false, watch: null },
    logLevel: 'error',
  })
  ;({ Playground } = await server.ssrLoadModule('/src/core/store.ts'))
  ;({ noteModule } = await server.ssrLoadModule('/src/objects/note/module.ts'))
})
beforeEach(() => {
  observers = []
})
after(async () => {
  await server?.close()
  if (originalResizeObserver === undefined) delete globalThis.ResizeObserver
  else globalThis.ResizeObserver = originalResizeObserver
})

const root = (clientWidth = 958, clientHeight = 758) => ({ clientWidth, clientHeight })
const note = (id) => ({ id, type: 'note', title: id, provenance: 'concept', config: { markdown: 'Test note' } })

function canvas(t) {
  const pg = new Playground([noteModule], {})
  t.after(() => pg.attach(null))
  pg.attach(root())
  assert.equal(pg.addObject(note('question'), 'agent', false).ok, true)
  assert.equal(pg.addObject(note('experiment'), 'agent', false).ok, true)
  pg.setObjectSize('question', 340, 265)
  pg.setObjectSize('experiment', 760, 752)
  pg.fitView()
  return pg
}

function assertVisible(pg, el) {
  const { viewport: v, objects } = pg.getState()
  for (const o of Object.values(objects)) {
    assert.ok(v.x + o.rect.x * v.zoom >= -0.01, `${o.id}: left edge`)
    assert.ok(v.y + o.rect.y * v.zoom >= -0.01, `${o.id}: top edge`)
    assert.ok(v.x + (o.rect.x + o.rect.w) * v.zoom <= el.clientWidth + 0.01, `${o.id}: right edge`)
    assert.ok(v.y + (o.rect.y + o.rect.h) * v.zoom <= el.clientHeight + 0.01, `${o.id}: bottom edge`)
  }
}

test('returning from Chat at the same size preserves the student viewport and objects', (t) => {
  const pg = canvas(t)
  const viewport = { x: -120, y: 75, zoom: 1.2 }
  pg.setViewport(viewport)
  pg.select('experiment')
  const objects = pg.getState().objects
  const previousObserver = observers.at(-1)

  pg.attach(null)
  assert.equal(previousObserver.disconnected, true)
  pg.attach(root())
  observers.at(-1).resize()

  assert.strictEqual(pg.getState().viewport, viewport)
  assert.strictEqual(pg.getState().objects, objects)
  assert.equal(pg.getState().selection, 'experiment')
})

test('returning after a sidebar/size change refits instead of clipping the right edge', (t) => {
  const pg = canvas(t)
  const objects = pg.getState().objects
  const smaller = root(702, 826)
  pg.attach(null)
  pg.attach(smaller)

  assertVisible(pg, smaller)
  assert.strictEqual(pg.getState().objects, objects)
})

test('resizing an attached canvas refits; duplicate size notifications preserve manual zoom', (t) => {
  const pg = canvas(t)
  const el = root()
  pg.attach(el)
  el.clientWidth = 626
  el.clientHeight = 638
  observers.at(-1).resize()
  assertVisible(pg, el)

  const viewport = { x: 12, y: 34, zoom: 1.4 }
  pg.setViewport(viewport)
  observers.at(-1).resize()
  assert.strictEqual(pg.getState().viewport, viewport)
})

test('a fit requested while Chat is open waits for the real container on return', (t) => {
  const pg = canvas(t)
  const viewport = pg.getState().viewport
  pg.attach(null)
  pg.fitView()
  assert.strictEqual(pg.getState().viewport, viewport)

  const el = root(626, 638)
  pg.attach(el)
  assertVisible(pg, el)
})

test('tutor additions while detached are fitted again after cards have their real size', (t) => {
  const pg = canvas(t)
  const viewport = pg.getState().viewport
  pg.attach(null)
  assert.equal(pg.addObject(note('follow-up')).ok, true)
  assert.strictEqual(pg.getState().viewport, viewport)

  const el = root()
  pg.attach(el)
  pg.setObjectSize('question', 340, 265)
  pg.setObjectSize('experiment', 760, 752)
  pg.setObjectSize('follow-up', 340, 1600)
  assertVisible(pg, el)
})

test('zero-sized containers and cards do not corrupt the saved view or measurements', (t) => {
  const pg = canvas(t)
  const viewport = pg.getState().viewport
  const rect = pg.getState().objects.experiment.rect
  pg.attach(null)
  const el = root(0, 0)
  pg.attach(el)
  pg.fitView()
  pg.focusObject('experiment')
  pg.setObjectSize('experiment', 0, 0)
  assert.strictEqual(pg.getState().viewport, viewport)
  assert.strictEqual(pg.getState().objects.experiment.rect, rect)

  el.clientWidth = 702
  el.clientHeight = 826
  observers.at(-1).resize()
  assertVisible(pg, el)
})

test('an obsolete observer cannot overwrite the viewport after a new root attaches', (t) => {
  const pg = canvas(t)
  const previousObserver = observers.at(-1)
  pg.attach(null)
  pg.attach(root(702, 826))
  const viewport = { x: 12, y: 34, zoom: 1.4 }
  pg.setViewport(viewport)
  previousObserver.resize()
  assert.strictEqual(pg.getState().viewport, viewport)
})
