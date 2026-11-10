import { createPlayground, presetModules, simulatedPython, TutorRunner, type Playground } from '@athena/playground'
import { askPlaygroundTutor, generateScene, getScene } from '../../../api/playground'
import { createKeyedStore } from '../../../lib/keyedStore'
import type { Offering } from '../../../types'
import { postToThread } from '../chat/chatStore'

/**
 * One Playground per offering: the canvas and the tutor that reacts to it.
 * Kept in memory in the learner's browser, like the chat thread; the tutor's
 * messages go into the unit's chat thread.
 */
interface Session {
  playground: Playground
  runner: TutorRunner
  /** The scene opened (or being opened), so a repeated request doesn't open it twice. */
  sceneId: string | null
}

const sessions = new Map<string, Session>()
const busy = createKeyedStore(false)
export const usePlaygroundBusy = busy.use

export function sessionFor(offering: Offering): Session {
  const existing = sessions.get(offering.id)
  if (existing) return existing
  const playground = createPlayground({ modules: presetModules, runtimes: { python: simulatedPython } })
  const runner = new TutorRunner(playground, {
    post: (m) => postToThread(offering.id, { role: 'tutor', content: m.text, via: 'playground' }),
    busy: (b) => busy.set(offering.id, b),
    ask: (request) => askPlaygroundTutor(offering, request),
  })
  runner.start()
  const session: Session = { playground, runner, sceneId: null }
  sessions.set(offering.id, session)
  return session
}

/** Open a scene the tutor offered (no-op if it's already open). */
export async function openScene(offering: Offering, sceneId: string) {
  const session = sessionFor(offering)
  if (session.sceneId === sceneId) return
  session.sceneId = sceneId
  const scene = await getScene(offering, sceneId)
  if (!scene) return
  const result = await session.runner.open(scene)
  if (!result.ok) {
    session.sceneId = null
    postToThread(offering.id, { role: 'tutor', content: `I couldn't set up this experiment: ${result.error}`, via: 'playground' })
  }
}

/**
 * The learner writes while on the Playground: ask to be shown, start a
 * different experiment, or ask about the selected object.
 */
export async function sendFromPlayground(offering: Offering, text: string) {
  const { playground, runner } = sessionFor(offering)
  postToThread(offering.id, { role: 'learner', content: text, via: 'playground' })
  if (/show me|demonstrat|right way/i.test(text) && runner.showMe()) return
  const offer = await generateScene(offering, text)
  if (offer && offer.sceneId !== sessionFor(offering).sceneId) return openScene(offering, offer.sceneId)
  runner.ask(playground.getState().selection, text)
}
