import type { Observation, PredictConfig } from '../../contracts'
import { defineModule } from '../types'
import { PredictView } from './PredictView'
import { s } from '../../core/schema'

export interface PredictState {
  choice: number | null
}

export const predictModule = defineModule<'predict', PredictState>({
  type: 'predict',
  label: 'Prediction',
  about: {
    summary:
      'A short multiple-choice question the student answers before experimenting, so a misconception shows up before it is tested. Write checks on `choose` for each option; the student can change their answer.',
    config: s.object({
      question: s.string('One sentence'),
      options: s.array(s.string(), 'Two to four short answers', 2, 4),
    }),
    actions: { choose: '{option}: pick an answer by its index' },
    observes: { on: ['choose'], fields: { choice: 'index of the answer', option: 'text of the answer' } },
  },
  width: 340,
  init: () => ({ choice: null }),
  edits: ['choose'],
  reduce: (state, action, config: PredictConfig) =>
    action.type === 'choose' && action.option >= 0 && action.option < config.options.length ? { choice: action.option } : state,
  observe: (state, action, config): Observation | null =>
    action.type === 'choose' && state.choice !== null ? { action: 'choose', choice: state.choice, option: config.options[state.choice] } : null,
  anchor: (action) => (action.type === 'choose' ? `option-${action.option}` : 'body'),
  summarize: (state, config) => ({ question: config.question, answer: state.choice === null ? null : config.options[state.choice] }),
  View: PredictView,
})
