import { defineModule } from '../types'
import { TitrationReadoutView } from './TitrationReadoutView'
import { s } from '../../core/schema'

/** A display node: readings, recorded trials and the titration curve of the rig in the same experiment. */
export const titrationReadoutModule = defineModule<'titration-readout', null>({
  type: 'titration-readout',
  label: 'Lab readout',
  about: {
    summary: 'Burette reading, pH, flask colour, pH–volume curve and recorded trials of the titration rig with the same experimentId.',
    config: s.empty(),
  },
  width: 440,
  init: () => null,
  reduce: (state) => state,
  summarize: () => ({ shows: 'the titration rig in the same experiment' }),
  View: TitrationReadoutView,
})
