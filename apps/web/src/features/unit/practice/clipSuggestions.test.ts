import { describe, expect, it } from 'vitest'
import type { LectureClip, LectureRecording } from '../../../types'
import { suggestClips } from './clipSuggestions'

const clip = (id: string, title: string, summary: string, topicId = 'insertion-sort', startS = 0): LectureClip => ({
  id, recordingId: 'rec', title, summary, topic: 'Insertion Sort', topicId, startS, endS: startS + 120,
})

const lecture: LectureRecording = {
  id: 'rec', offeringId: 'cse5alg-2026-s2', title: 'Insertion Sort', week: 2, durationS: 6600, status: 'ready',
  clips: [
    clip('rec-01', 'Insertion sort through playing cards', 'Sorting a hand of cards one at a time.', 'insertion-sort', 41),
    clip('rec-07', 'Best-case insertion sort complexity', 'On sorted input each element is compared once.', 'insertion-sort', 1307),
    clip('rec-08', 'Worst-case insertion sort complexity', 'Reversed input shifts every element past all earlier ones.', 'insertion-sort', 1421),
    clip('rec-20', 'Shell sort complexity and gap selection', 'Gap sequences change the running time.', 'complexity-search', 4556),
  ],
}

describe('suggestClips', () => {
  it('ranks same-topic clips by shared wording', () => {
    const out = suggestClips([lecture], {
      clipIds: [], topicId: 'insertion-sort',
      text: 'What is the worst-case time of insertion sort? Reversed input makes every element shift.',
    })
    expect(out[0].clip.id).toBe('rec-08')
    expect(out[0].reason).toBe('topic')
  })

  it('puts clips the question was written from first', () => {
    const out = suggestClips([lecture], { clipIds: ['rec-01'], topicId: 'insertion-sort', text: 'worst case reversed input' })
    expect(out.map((s) => s.clip.id)).toEqual(['rec-01', 'rec-08'])
    expect(out[0].reason).toBe('linked')
  })

  it('ignores other topics and clips sharing no words', () => {
    expect(suggestClips([lecture], { clipIds: [], topicId: 'hash-tables', text: 'linear probing slot' })).toEqual([])
    const out = suggestClips([lecture], { clipIds: [], topicId: 'insertion-sort', text: 'stable equal keys order' })
    expect(out).toEqual([])
  })

  it('respects the limit', () => {
    const out = suggestClips([lecture], { clipIds: [], topicId: 'insertion-sort', text: 'insertion sort complexity input element' }, 1)
    expect(out).toHaveLength(1)
  })
})
