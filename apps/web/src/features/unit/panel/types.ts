import type { DocumentReference, LectureClip, LectureRecording, SandboxSession } from '../../../types'

/**
 * Anything that can open in the unit's side panel. Add a kind here and a
 * renderer in ./renderers.ts; nothing else in the layout changes.
 */
export type PanelContent =
  | { kind: 'sandbox'; session: SandboxSession }
  | { kind: 'clip'; clip: LectureClip; lecture: Pick<LectureRecording, 'id' | 'title' | 'week' | 'durationS'> }
  | { kind: 'source'; source: DocumentReference }

export type PanelKind = PanelContent['kind']
