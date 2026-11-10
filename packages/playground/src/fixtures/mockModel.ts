import type { TutorResponse } from '../contracts'
import type { TutorRequest } from '../tutor/runner'
import { demoScenes } from './index'

/**
 * TEST DOUBLES for the model, until one is connected. `prepareScene` stands in
 * for generating a scene from the student's prompt; `mockAsk` for answering
 * what the scene didn't prepare.
 */
export function prepareScene(prompt: string, exceptId?: string) {
  return demoScenes.find((d) => d.match.test(prompt) && d.scene.id !== exceptId)?.scene ?? null
}

export async function mockAsk(request: TutorRequest): Promise<TutorResponse> {
  await new Promise((r) => setTimeout(r, 700))
  switch (request.kind) {
    case 'question': {
      const obj = request.snapshot.objects.find((o) => o.id === request.objectId)
      const about = obj ? `About “${obj.title}”` : 'About the canvas'
      const state = obj ? JSON.stringify(obj.state).slice(0, 160) : `${request.snapshot.objects.length} objects`
      return { say: `(Mock: the real tutor answers this once a model is connected.) ${about}, you asked: “${request.text}”. What I can read from the canvas: ${state}…` }
    }
    case 'unmatched':
      return { say: `(Mock reply.) I saw what you did: ${JSON.stringify(request.observation)}. What did you expect to happen?` }
    case 'misconception':
      return { say: `(Mock reply.) Misconception “${request.checkId}” has no prepared response.` }
  }
}
