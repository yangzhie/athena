import type { Scene, TutorRequest, TutorResponse } from '@athena/playground'
import { demoScenes, mockAsk, prepareScene } from '@athena/playground/fixtures'
import type { Offering, PlaygroundOffer } from '../types'

/** Demo scenes are local to a learning session, not shared across an offering's chats. */
const generated = new Map<string, Map<string, Scene>>()
const scope = (offering: Offering, sessionId: string) => JSON.stringify([offering.id, sessionId])

/**
 * A Playground scene for the learner's question, or null when trying things
 * out wouldn't help. Mock: picks a prepared scene. The real version asks the
 * agent to compose one from the component catalog and the unit's material;
 * the agent validates it (`validateScene`) and repairs it before returning.
 */
export async function generateScene(offering: Offering, question: string, sessionId: string): Promise<PlaygroundOffer | null> {
  const scene = prepareScene(question)
  if (!scene) return null
  const key = scope(offering, sessionId)
  const scenes = generated.get(key) ?? new Map<string, Scene>()
  scenes.set(scene.id, scene)
  generated.set(key, scenes)
  return { sceneId: scene.id, title: scene.title, goal: scene.goal }
}

export async function getScene(offering: Offering, sceneId: string, sessionId: string): Promise<Scene | null> {
  return generated.get(scope(offering, sessionId))?.get(sceneId) ?? demoScenes.find((d) => d.scene.id === sceneId)?.scene ?? null
}

export function forgetScenes(offering: Offering, sessionId: string) {
  generated.delete(scope(offering, sessionId))
}

/**
 * The tutor's answer to something the scene didn't prepare: a question about
 * the canvas, an unmatched action. Mock; the real version sends the request
 * (with the canvas snapshot) to the agent.
 */
export function askPlaygroundTutor(_offering: Offering, request: TutorRequest): Promise<TutorResponse> {
  return mockAsk(request)
}

/** Prompts that lead to a Playground, for the empty state. */
export function playgroundSuggestions() {
  return demoScenes.map((d) => d.prompt)
}
