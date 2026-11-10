import type { LectureClip, LectureRecording } from '../../../types'

export interface ClipSuggestion {
  clip: LectureClip
  lecture: LectureRecording
  /** linked = the question was written from this clip; topic = same topic, matched by wording. */
  reason: 'linked' | 'topic'
}

const STOP = new Set(
  'the a an and or of to in on for is are was be by with as at it its this that what which why how when does do you your from into than then'.split(' '),
)

function words(text: string): Set<string> {
  return new Set(
    text
      .toLowerCase()
      .split(/[^a-z0-9²]+/)
      .filter((w) => w.length > 2 && !STOP.has(w))
      .map((w) => w.replace(/(ing|es|s)$/, '')),
  )
}

/**
 * Lecture clips to rewatch after getting a question wrong.
 *
 * Clips the question was written from come first. Then clips on the same topic,
 * ranked by how many words their title and summary share with the question and
 * explanation; a same-topic clip must share at least one. Pass only clips the
 * student can see (approved ones).
 */
export function suggestClips(
  lectures: LectureRecording[],
  question: { clipIds: string[]; topicId: string; text: string },
  limit = 2,
): ClipSuggestion[] {
  const target = words(question.text)
  const scored: { s: ClipSuggestion; score: number }[] = []
  for (const lecture of lectures) {
    for (const clip of lecture.clips) {
      if (question.clipIds.includes(clip.id)) {
        scored.push({ s: { clip, lecture, reason: 'linked' }, score: 1000 })
      } else if (clip.topicId && clip.topicId === question.topicId) {
        const shared = [...words(`${clip.title} ${clip.summary}`)].filter((w) => target.has(w)).length
        if (shared > 0) scored.push({ s: { clip, lecture, reason: 'topic' }, score: shared })
      }
    }
  }
  return scored
    .sort((a, b) => b.score - a.score || a.s.clip.startS - b.s.clip.startS)
    .slice(0, limit)
    .map((x) => x.s)
}
