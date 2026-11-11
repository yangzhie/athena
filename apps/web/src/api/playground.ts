import type { ObjectSpec, Playground, Scene, TutorRequest, TutorResponse } from '@athena/playground'
import type { Offering, PlaygroundOffer } from '../types'
import { call } from './client'
import { operationCall, recoverPlaygroundTurn } from './operations'

export interface Execution {
  id: string; object_id: string; run_id: number; actor: 'agent' | 'student'
  state: 'queued' | 'running' | 'finished' | 'unavailable' | 'cancelled'
  result: { ok: boolean; stdout: string; error?: { type: string; message: string } } | null
  error: string | null
  interpreted?: boolean
}
export interface CanvasView {
  catalog_version: string
  revision: number
  checkpoint: ReturnType<Playground['checkpoint']> | null
  snapshot: ReturnType<Playground['snapshot']> | null
  executions?: Execution[]
  replacements?: { id: string; scene: Scene }[]
}
export const playgroundBase = (offering: Offering, sessionId: string) => `/units/${encodeURIComponent(offering.id)}/sessions/${encodeURIComponent(sessionId)}/playground`

export async function getCanvas(offering: Offering, sessionId: string): Promise<CanvasView> {
  const base = playgroundBase(offering, sessionId)
  await recoverPlaygroundTurn(`${base}/turns`)
  return call(base)
}
export function commitCanvas(offering: Offering, sessionId: string, revision: number, command: object, operationId: string = crypto.randomUUID()) {
  return call<CanvasView>(`${playgroundBase(offering, sessionId)}/commands`, { method: 'POST', body: JSON.stringify({ operation_id: operationId, revision, command, catalog_version: '1.0.0' }) })
}
/** Opens one of the Playground package's hand-built scenes by id (no model involved). */
export function openPreparedScene(offering: Offering, sessionId: string, sceneId: string, revision: number, operationId: string = crypto.randomUUID()) {
  return call<CanvasView>(`${playgroundBase(offering, sessionId)}/prepared/${encodeURIComponent(sceneId)}`, {
    method: 'POST', body: JSON.stringify({ operation_id: operationId, revision, command: {}, catalog_version: '1.0.0' }),
  })
}
export function playgroundTurn(offering: Offering, sessionId: string, text: string, kind: 'question' | 'scene' | 'event' | 'execution' = 'question') {
  return operationCall(`${playgroundBase(offering, sessionId)}/turns`, { text, kind })
}
export function decideReplacement(offering: Offering, sessionId: string, proposalId: string, decision: 'accept' | 'reject', revision: number, operationId: string = crypto.randomUUID()) {
  return call<CanvasView>(`${playgroundBase(offering, sessionId)}/replacements/${encodeURIComponent(proposalId)}/${decision}`, {
    method: 'POST', body: JSON.stringify({ operation_id: operationId, revision, command: {}, catalog_version: '1.0.0' }),
  })
}
export function cancelExecution(offering: Offering, sessionId: string, executionId: string) {
  return call(`${playgroundBase(offering, sessionId)}/executions/${encodeURIComponent(executionId)}`, { method: 'DELETE' })
}
/** Adapter signatures retained. Read existing scenes; generation is student initiated. */
export async function generateScene(offering: Offering, _question: string, sessionId: string): Promise<PlaygroundOffer | null> {
  const view = await getCanvas(offering, sessionId)
  return view.snapshot?.scene ? { sceneId: view.snapshot.scene.id, title: view.snapshot.scene.title, goal: view.snapshot.scene.goal } : null
}
export async function getScene(offering: Offering, sceneId: string, sessionId: string): Promise<Scene | null> {
  const view = await getCanvas(offering, sessionId)
  if (view.snapshot?.scene?.id !== sceneId || !view.checkpoint) return null
  return { ...view.snapshot.scene, objects: view.checkpoint.state.order.map((id) => view.checkpoint!.state.objects[id] as ObjectSpec), checks: view.checkpoint.state.checks }
}
export function forgetScenes(offering: Offering, sessionId: string) { void offering; void sessionId /* Server deletion owns persistence. */ }
export async function askPlaygroundTutor(offering: Offering, request: TutorRequest, sessionId?: string): Promise<TutorResponse> {
  if (!sessionId) throw new Error('Learning session is required')
  await playgroundTurn(offering, sessionId, request.kind === 'question' ? request.text : 'Help me reason about the last committed action.', request.kind === 'question' ? 'question' : 'event')
  return { say: '' } // The saved session transcript is the sole source of tutor messages.
}
export const playgroundSuggestions = () => [
  { label: 'Build an experiment', text: 'Build an experiment for my current learning goal.' },
  { label: 'Explore Python', text: 'Help me test a small Python example for this goal.' },
]

export function interpretExecution(offering: Offering, sessionId: string, executionId: string) {
  return call(`${playgroundBase(offering, sessionId)}/executions/${encodeURIComponent(executionId)}/interpret`, { method: 'POST' })
}
