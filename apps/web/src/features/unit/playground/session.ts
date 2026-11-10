import { createPlayground, presetModules, simulatedPython, TutorRunner, type Playground } from '@athena/playground'
import { askPlaygroundTutor, forgetScenes, generateScene, getScene } from '../../../api/playground'
import { createKeyedStore } from '../../../lib/keyedStore'
import type { Offering } from '../../../types'
import { getThread, postToThread } from '../chat/chatStore'

/** One local demo canvas per learning session, retained when switching back to its chat. */
interface Session {
  playground: Playground
  runner: TutorRunner
  /** The scene opened (or being opened), so a repeated request doesn't open it twice. */
  sceneId: string | null
  dispose: () => void
}

const sessions = new Map<string, Session>()
const busy = createKeyedStore(false)
export const usePlaygroundBusy = busy.use

export function sessionFor(offering: Offering, sessionId: string): Session {
  const thread = getThread(sessionId)
  if (thread.status !== 'ready' || thread.session?.offeringId !== offering.id) {
    throw new Error('Load this learning session before opening its Playground.')
  }
  const existing = sessions.get(sessionId)
  if (existing) return existing
  const playground = createPlayground({ modules: presetModules, runtimes: { python: simulatedPython } })
  let active = true
  const runner = new TutorRunner(playground, {
    post: (m) => { if (active) postToThread(sessionId, { role: 'tutor', content: m.text }) },
    busy: (b) => { if (active) busy.set(sessionId, b) },
    ask: (request) => askPlaygroundTutor(offering, request),
  })
  const unsubscribe = runner.start()
  const session: Session = {
    playground, runner, sceneId: null,
    dispose: () => {
      active = false
      unsubscribe()
      playground.attach(null)
      forgetScenes(offering, sessionId)
      busy.set(sessionId, false)
    },
  }
  sessions.set(sessionId, session)
  return session
}

export function forgetPlayground(sessionId: string) {
  sessions.get(sessionId)?.dispose()
  sessions.delete(sessionId)
}

/** Open a scene the tutor offered (no-op if it's already open). */
export async function openScene(offering: Offering, sessionId: string, sceneId: string) {
  const session = sessionFor(offering, sessionId)
  if (session.sceneId === sceneId) return
  session.sceneId = sceneId
  try {
    const scene = await getScene(offering, sceneId, sessionId)
    if (sessions.get(sessionId) !== session || session.sceneId !== sceneId) return
    if (!scene) throw new Error('This demo scene is unavailable. Choose another experiment below.')
    const result = await session.runner.open(scene)
    if (!result.ok) throw new Error(result.error)
  } catch (e) {
    if (sessions.get(sessionId) !== session || session.sceneId !== sceneId) return
    session.sceneId = null
    postToThread(sessionId, { role: 'tutor', content: `I couldn't set up this experiment: ${e instanceof Error ? e.message : String(e)}` })
  }
}

/** Demo questions stay local; agent activity answers still use the real session API. */
export async function sendFromPlayground(offering: Offering, sessionId: string, text: string) {
  const session = sessionFor(offering, sessionId)
  if (busy.get(sessionId) || getThread(sessionId).sending) return
  const { playground, runner } = session
  postToThread(sessionId, { role: 'learner', content: text })
  if (/show me|demonstrat|right way/i.test(text) && runner.showMe()) return
  const offer = await generateScene(offering, text, sessionId)
  if (sessions.get(sessionId) !== session) return
  if (offer && offer.sceneId !== session.sceneId) return openScene(offering, sessionId, offer.sceneId)
  runner.ask(playground.getState().selection, text)
}
