import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../../api/client'
import { generateScene } from '../../../api/playground'
import * as api from '../../../api/sessions'
import type { ChatMessage, LearningSession, Offering } from '../../../types'
import { openActivityId } from './activity'
import { answer, continueLearning, forgetThread, getThread, loadThread, postToThread, seedThread, sendMessage, stopWaiting, suggestPlayground } from './chatStore'

vi.mock('../../../api/sessions')
vi.mock('../../../api/playground')

const offering: Offering = { id: 'offering-a', unit: { code: 'TEST', title: 'Test' }, year: 2026, semester: 'Semester 1', suggestions: [] }
const session: LearningSession = {
  id: 'session-a', offeringId: offering.id, goal: 'Data cleaning', title: 'Data cleaning',
  createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z', shared: false,
}
const message = (id: string): ChatMessage => ({ id, role: 'tutor', content: id, createdAt: '2026-01-01T00:00:00Z' })
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

beforeEach(() => {
  vi.resetAllMocks()
  seedThread(session, [message('opening')])
  seedThread({ ...session, id: 'session-b' }, [])
  vi.mocked(generateScene).mockResolvedValue(null)
})

describe('API sessions with local Playground messages', () => {
  it('keeps two sessions in the same offering isolated', () => {
    postToThread(session.id, { role: 'learner', content: 'local experiment' })
    expect(getThread(session.id).messages.at(-1)).toMatchObject({ via: 'playground', content: 'local experiment' })
    expect(getThread('session-b').messages).toEqual([])
    expect(getThread(offering.id).messages).toEqual([])
  })

  it('retains local messages added while an API refresh was in flight', async () => {
    const response = deferred<Awaited<ReturnType<typeof api.getSession>>>()
    vi.mocked(api.getSession).mockReturnValue(response.promise)
    const loading = loadThread(offering.id, session.id, { refresh: true })
    postToThread(session.id, { role: 'tutor', content: 'demo feedback' })
    response.resolve({ session, messages: [message('opening'), message('lecturer-reply')] })
    await loading
    expect(getThread(session.id).messages.map((m) => m.content)).toEqual(['opening', 'lecturer-reply', 'demo feedback'])
    await loadThread(offering.id, session.id, { refresh: true })
    expect(getThread(session.id).messages.filter((m) => m.via)).toHaveLength(1)
  })

  it('retains local messages across a transient API failure and retry', async () => {
    postToThread(session.id, { role: 'learner', content: 'my attempt' })
    vi.mocked(api.getSession).mockRejectedValueOnce(new ApiError(0, 'Offline'))
    await loadThread(offering.id, session.id, { refresh: true })
    expect(getThread(session.id).status).toBe('error')
    vi.mocked(api.getSession).mockResolvedValue({ session, messages: [message('opening')] })
    await loadThread(offering.id, session.id)
    expect(getThread(session.id).messages.at(-1)?.content).toBe('my attempt')
  })

  it.each([401, 403, 404])('clears private cached messages after API status %i', async (status) => {
    postToThread(session.id, { role: 'learner', content: 'private' })
    vi.mocked(api.getSession).mockRejectedValue(new ApiError(status, 'Unavailable'))
    await loadThread(offering.id, session.id, { refresh: true })
    expect(getThread(session.id).messages).toEqual([])
    expect(getThread(session.id).session).toBeUndefined()
  })

  it('does not resurrect a deleted session when a load finishes late', async () => {
    const response = deferred<Awaited<ReturnType<typeof api.getSession>>>()
    vi.mocked(api.getSession).mockReturnValue(response.promise)
    const loading = loadThread(offering.id, session.id, { refresh: true })
    forgetThread(session.id)
    postToThread(session.id, { role: 'tutor', content: 'late demo reply' })
    response.resolve({ session, messages: [message('opening')] })
    await loading
    expect(getThread(session.id)).toMatchObject({ status: 'missing', messages: [] })
  })

  it('sends only the new text to the real API and keeps demo messages local', async () => {
    postToThread(session.id, { role: 'learner', content: 'private demo text' })
    const saved = [message('real agent reply')]
    vi.mocked(api.sendSessionMessage).mockResolvedValue(saved)
    expect(await sendMessage(offering.id, session.id, 'Explain this')).toEqual(saved)
    expect(api.sendSessionMessage).toHaveBeenCalledExactlyOnceWith(offering.id, session.id, 'Explain this', expect.any(AbortSignal))
    expect(getThread(session.id).messages.map((m) => m.content)).toEqual(['opening', 'real agent reply', 'private demo text'])
    expect(getThread(session.id).sending).toBe(false)
  })

  it('does not let an older refresh erase a completed API turn', async () => {
    const response = deferred<Awaited<ReturnType<typeof api.getSession>>>()
    vi.mocked(api.getSession).mockReturnValue(response.promise)
    const loading = loadThread(offering.id, session.id, { refresh: true })
    vi.mocked(api.sendSessionMessage).mockResolvedValue([message('new reply')])
    await sendMessage(offering.id, session.id, 'Next question')
    response.resolve({ session, messages: [message('opening')] })
    await loading
    expect(getThread(session.id).messages.some((m) => m.content === 'new reply')).toBe(true)
  })

  it('ignores a late API reply after the session has been deleted', async () => {
    const response = deferred<ChatMessage[]>()
    vi.mocked(api.sendSessionMessage).mockReturnValue(response.promise)
    const sending = sendMessage(offering.id, session.id, 'Question')
    forgetThread(session.id)
    response.resolve([message('too late')])
    await sending
    expect(getThread(session.id)).toMatchObject({ status: 'missing', messages: [] })
  })

  it('deduplicates suggestions without replacing the real tutor message', async () => {
    vi.mocked(generateScene).mockResolvedValue({ sceneId: 'cleaning', title: 'Cleaning', goal: 'Try cleaning' })
    await Promise.all([suggestPlayground(offering, session.id, 'code'), suggestPlayground(offering, session.id, 'code')])
    const messages = getThread(session.id).messages
    expect(messages[0]).toEqual(message('opening'))
    expect(messages.filter((m) => m.playground)).toHaveLength(1)
    expect(messages[1].via).toBe('playground')
    expect(api.sendSessionMessage).not.toHaveBeenCalled()
  })

  it('does not suggest a scene for another offering or a deleted session', async () => {
    await suggestPlayground({ ...offering, id: 'other-offering' }, session.id, 'code')
    forgetThread(session.id)
    await suggestPlayground(offering, session.id, 'code')
    expect(generateScene).not.toHaveBeenCalled()
  })

  it('preserves question state and real answer routing with demo messages in between', async () => {
    const question: ChatMessage = {
      ...message('question'), activity: { kind: 'question', activity_id: 'activity-1', question: {
        question_id: 'q1', kind: 'open_ended', concept_id: 'cleaning', prompt: 'Why?', difficulty: 'easy',
      } },
    }
    seedThread(session, [question])
    postToThread(session.id, { role: 'tutor', content: 'Try the canvas' })
    expect(openActivityId(getThread(session.id).messages)).toBe('activity-1')
    const input = { questionId: 'q1', text: 'Reason', shown: 'Reason' }
    vi.mocked(api.answerQuestion).mockRejectedValueOnce(new ApiError(503, 'Try again'))
    await answer(offering.id, session.id, input)
    expect(openActivityId(getThread(session.id).messages)).toBe('activity-1')
    vi.mocked(api.answerQuestion).mockResolvedValue([{ ...message('answer'), role: 'learner', answerFor: 'q1' }])
    await answer(offering.id, session.id, input)
    expect(api.answerQuestion).toHaveBeenLastCalledWith(offering.id, session.id, input, expect.any(AbortSignal))
    expect(openActivityId(getThread(session.id).messages)).toBeNull()
  })

  it('continues agent activities through the session API', async () => {
    vi.mocked(api.continueSession).mockResolvedValue([message('next step')])
    await continueLearning(offering.id, session.id, 'activity-1')
    expect(api.continueSession).toHaveBeenCalledExactlyOnceWith(offering.id, session.id, 'activity-1', expect.any(AbortSignal))
    expect(getThread(session.id).messages.at(-1)?.content).toBe('next step')
  })

  it('still supports stopping an API turn', async () => {
    vi.mocked(api.sendSessionMessage).mockImplementation((_offering, _session, _text, signal) =>
      new Promise((_resolve, reject) => signal?.addEventListener('abort', () => reject(new DOMException('Stopped', 'AbortError')))),
    )
    const sending = sendMessage(offering.id, session.id, 'Question')
    stopWaiting(session.id)
    await sending
    expect(getThread(session.id).sending).toBe(false)
    expect(getThread(session.id).error).toBeUndefined()
    expect(getThread(session.id).messages.some((m) => m.role === 'tutor' && !m.content)).toBe(false)
  })
})
