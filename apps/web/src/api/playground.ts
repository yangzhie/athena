import type { Scene, TutorRequest, TutorResponse } from '@athena/playground'
import { demoScenes, mockAsk, prepareScene } from '@athena/playground/fixtures'
import type { Offering, PlaygroundOffer } from '../types'

/** Scenes generated in this session, by id. They belong to the learner's environment only. */
const generated = new Map<string, Scene>()

/**
 * A Playground scene for the learner's question, or null when trying things
 * out wouldn't help. Mock: picks a prepared scene. The real version asks the
 * agent to compose one from the component catalog and the unit's material;
 * the agent validates it (`validateScene`) and repairs it before returning.
 */
export async function generateScene(_offering: Offering, question: string): Promise<PlaygroundOffer | null> {
  const scene = prepareScene(question)
  if (!scene) return null
  generated.set(scene.id, scene)
  return { sceneId: scene.id, title: scene.title, goal: scene.goal }
}

export async function getScene(_offering: Offering, sceneId: string): Promise<Scene | null> {
  return generated.get(sceneId) ?? demoScenes.find((d) => d.scene.id === sceneId)?.scene ?? null
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
