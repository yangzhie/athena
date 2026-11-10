import type { NoteConfig } from '../../contracts'
import { defineModule } from '../types'
import { NoteView } from './NoteView'
import { s } from '../../core/schema'

export const noteModule = defineModule<'note', null>({
  type: 'note',
  label: 'Note',
  about: {
    summary: 'A short Markdown note: the question, a procedure, or a concept explanation. Keep it under ~120 words.',
    config: s.object({ markdown: s.string('Markdown text; **bold** and `code` are supported') }),
  },
  width: 340,
  init: () => null,
  reduce: (state) => state,
  summarize: (_state, config: NoteConfig) => ({ text: config.markdown }),
  View: NoteView,
})
