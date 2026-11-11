import { describe, expect, it } from 'vitest'
import type { AgentActivity, ChatMessage } from '../../../types'
import { lessonProgress } from './lessonProgress'

let n = 0
const tutor = (activity: AgentActivity): ChatMessage => ({ id: `m${++n}`, role: 'tutor', content: '', activity, createdAt: '' })
const question = (id: string) => tutor({ kind: 'question', activity_id: id, question: { kind: 'multiple_choice', question_id: id, concept_id: 'c', prompt: '?', difficulty: 'beginner' } })
const feedback = (outcome: 'correct' | 'incorrect') => tutor({ kind: 'feedback', activity_id: `f${n}`, text: '', content: { outcome, message: '' } })
const explanation = tutor({ kind: 'explanation', activity_id: 'e', text: 'Teach' })

describe('lessonProgress', () => {
  it('starts in diagnosis and numbers questions', () => {
    const p = lessonProgress([question('q1'), feedback('incorrect'), question('q2')])
    expect(p.stage).toBe('diagnose')
    expect(p.questionNumber).toEqual({ q1: 1, q2: 2 })
    expect([p.asked, p.answered, p.correct]).toEqual([2, 1, 0])
  })

  it('moves to teaching, then to checks after teaching, then done', () => {
    const msgs = [question('q1'), feedback('incorrect'), explanation]
    expect(lessonProgress(msgs).stage).toBe('teach')
    msgs.push(question('q2'), feedback('correct'))
    expect(lessonProgress(msgs).stage).toBe('check')
    expect(lessonProgress(msgs).correct).toBe(1)
    msgs.push(tutor({ kind: 'completion', activity_id: 'done', text: 'Done' }))
    expect(lessonProgress(msgs).stage).toBe('done')
  })

  it('ignores learner messages and plain tutor text', () => {
    expect(lessonProgress([{ id: 'x', role: 'learner', content: 'hi', createdAt: '' }]).asked).toBe(0)
  })
})
