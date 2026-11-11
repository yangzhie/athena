import { createPlayground, presetModules, type Playground } from '@athena/playground'
import { ApiError } from '../../../api/client'
import { commitCanvas, decideReplacement, getCanvas, interpretExecution, openPreparedScene, playgroundTurn, type CanvasView } from '../../../api/playground'
import { isPrepared } from './preparedScenes'
import { createKeyedStore } from '../../../lib/keyedStore'
import type { Offering } from '../../../types'
import { getThread, loadThread } from '../chat/chatStore'

type Command = Parameters<typeof commitCanvas>[3]
interface Session {
  playground: Playground
  revision: number
  sceneId: string | null
  queue: Promise<void>
  pending?: { command: Command; revision: number; id: string }
  active: boolean
  dispose: () => void
}
const sessions = new Map<string, Session>()
const busy = createKeyedStore(false)
const details = createKeyedStore<{ error?: string; executions: NonNullable<CanvasView['executions']>; replacements: NonNullable<CanvasView['replacements']> }>({ executions: [], replacements: [] })
export const usePlaygroundBusy = busy.use
export const usePlaygroundDetails = details.use

export function sessionFor(offering: Offering, sessionId: string): Session {
  const thread = getThread(sessionId)
  if (thread.status !== 'ready' || thread.session?.offeringId !== offering.id) throw new Error('Load this learning session before opening its Playground.')
  const existing = sessions.get(sessionId)
  if (existing) return existing
  const playground = createPlayground({ modules: presetModules, runtimes: { python: { provenance: 'real-run', run: async () => { throw new Error('Use the session-authorised execution service') } } } })
  const session: Session = { playground, revision: 0, sceneId: null, queue: Promise.resolve(), active: true,
    dispose: () => { session.active = false; playground.setCommitHandler(null); playground.attach(null); busy.set(sessionId, false) } }
  sessions.set(sessionId, session)
  playground.setCommitHandler((command) => serial(sessionId, async () => {
    const pending = session.pending ?? { command, revision: session.revision, id: crypto.randomUUID() }
    if (session.pending && JSON.stringify(session.pending.command) !== JSON.stringify(command)) throw new Error('Retry the previous canvas change first.')
    session.pending = pending
    const result = await commitCanvas(offering, sessionId, pending.revision, pending.command, pending.id)
    session.pending = undefined
    apply(sessionId, result)
    // Only server-observed actions trigger tutoring; no client-reported success establishes mastery.
    const recent = result.checkpoint?.events.slice(-3) ?? []
    if (command.kind === 'accept' || command.kind === 'reject' || recent.some((e) => e.kind === 'unmatched' || (e.kind === 'check' && e.verdict === 'misconception'))) {
      await playgroundTurn(offering, sessionId, command.kind === 'reject' ? 'I rejected the proposal; preserve my work.' : 'Help me reason about the latest committed action.', 'event')
      await loadThread(offering.id, sessionId, { refresh: true })
      apply(sessionId, await getCanvas(offering, sessionId))
    }
  }))
  return session
}
function apply(sessionId: string, view: CanvasView) {
  const session = sessions.get(sessionId)
  if (!session?.active || view.revision < session.revision) return
  session.revision = view.revision
  const sceneId = view.snapshot?.scene?.id ?? null
  const newScene = sceneId !== null && sceneId !== session.sceneId
  session.sceneId = sceneId
  if (view.checkpoint) {
    view.checkpoint.state.viewport = session.playground.getState().viewport
    session.playground.restore(view.checkpoint)
    // Keep the student's pan/zoom within a scene, but show all of a newly opened one.
    if (newScene) session.playground.fitView()
  }
  const previous = details.get(sessionId)
  details.set(sessionId, { executions: view.executions ?? previous.executions, replacements: view.replacements ?? previous.replacements })
}
async function serial(sessionId: string, work: () => Promise<void>) {
  const session = sessions.get(sessionId)
  if (!session) return
  session.queue = session.queue.then(async () => {
    if (!session.active) return
    busy.set(sessionId, true)
    try { await work() } catch (error) {
      if (session.active) details.set(sessionId, { ...details.get(sessionId), error: error instanceof Error ? error.message : String(error) })
      if (error instanceof ApiError && [401, 403, 404, 409, 413, 422].includes(error.status)) session.pending = undefined
    } finally { if (session.active) busy.set(sessionId, false) }
  })
  return session.queue
}
export async function restoreCanvas(offering: Offering, sessionId: string) {
  sessionFor(offering, sessionId)
  if (busy.get(sessionId)) return
  return serial(sessionId, async () => {
    const view = await getCanvas(offering, sessionId)
    apply(sessionId, view)
    const finished = view.executions?.find((job) => job.state === 'finished' && job.interpreted === false)
    if (finished) {
      await interpretExecution(offering, sessionId, finished.id)
      await loadThread(offering.id, sessionId, { refresh: true })
    }
  })
}
export async function retryCanvas(offering: Offering, sessionId: string) {
  const session = sessionFor(offering, sessionId)
  if (session.pending) {
    const pending = session.pending
    return serial(sessionId, async () => {
      apply(sessionId, await commitCanvas(offering, sessionId, pending.revision, pending.command, pending.id))
      session.pending = undefined
    })
  }
  return restoreCanvas(offering, sessionId)
}
export function forgetPlayground(sessionId: string) {
  sessions.get(sessionId)?.dispose()
  sessions.delete(sessionId)
  details.set(sessionId, { executions: [], replacements: [] })
}
/** `?scene=<id>`: show the canvas, and open that prepared scene if the canvas is still empty. */
export async function openScene(offering: Offering, sessionId: string, sceneId: string) {
  await restoreCanvas(offering, sessionId)
  const session = sessionFor(offering, sessionId)
  if (!session.sceneId && isPrepared(sceneId)) return openPrepared(offering, sessionId, sceneId)
}
/** Opens a prepared scene, replacing what's on the canvas (callers confirm first if there is something). */
export async function openPrepared(offering: Offering, sessionId: string, sceneId: string) {
  const session = sessionFor(offering, sessionId)
  return serial(sessionId, async () => {
    if (session.sceneId === sceneId) return
    apply(sessionId, await openPreparedScene(offering, sessionId, sceneId, session.revision))
  })
}
export async function sendFromPlayground(offering: Offering, sessionId: string, text: string) {
  const session = sessionFor(offering, sessionId)
  if (getThread(sessionId).sending) return
  // A snapshot refresh may start between rendering and submission; queue the message behind it.
  return serial(sessionId, async () => {
    await playgroundTurn(offering, sessionId, text, session.sceneId ? 'question' : 'scene')
    if (!session.active) return
    apply(sessionId, await getCanvas(offering, sessionId))
    await loadThread(offering.id, sessionId, { refresh: true })
  })
}
export async function replacementDecision(offering: Offering, sessionId: string, proposalId: string, decision: 'accept' | 'reject') {
  const session = sessionFor(offering, sessionId)
  return serial(sessionId, async () => {
    await decideReplacement(offering, sessionId, proposalId, decision, session.revision)
    apply(sessionId, await getCanvas(offering, sessionId))
    await playgroundTurn(offering, sessionId, decision === 'accept' ? 'I accepted the replacement.' : 'I rejected the replacement; keep my work.', 'event')
    await loadThread(offering.id, sessionId, { refresh: true })
  })
}
