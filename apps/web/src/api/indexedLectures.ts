import type { LectureRecording } from '../types'

/**
 * Lectures indexed on this machine by workers/indexer (`index-lecture --offering ...`).
 *
 * Those clips.json files contain lecture transcripts (lecturer IP) and are
 * gitignored, so this only finds anything in a local checkout that has run the
 * indexer; everywhere else it's empty and the mocks are used. Never deploy a
 * build made from a checkout with indexed lectures in it.
 */

/** The parts of the indexer's clips.json (IndexResult) the app uses. */
interface IndexedFile {
  recordingId: string
  title: string
  durationS: number
  status: LectureRecording['status']
  offeringId?: string | null
  week?: number | null
  clips: {
    id: string
    recordingId: string
    title: string
    topic: string
    summary: string
    startS: number
    endS: number
    approved: boolean
  }[]
}

const files = import.meta.glob<IndexedFile>('../../../../workers/indexer/data/*/clips.json', {
  eager: true,
  import: 'default',
})

export const indexedLectures: LectureRecording[] = Object.values(files)
  .filter((f) => f.offeringId)
  .map((f) => ({
    id: f.recordingId,
    offeringId: f.offeringId!,
    title: f.title,
    week: f.week ?? 0,
    durationS: f.durationS,
    status: f.status,
    draft: f.clips.some((c) => !c.approved),
    clips: f.clips.map((c) => ({
      id: c.id,
      recordingId: c.recordingId,
      title: c.title,
      topic: c.topic,
      summary: c.summary,
      startS: c.startS,
      endS: c.endS,
    })),
  }))
