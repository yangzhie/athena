import { defineModule } from '../types'
import { ForceReadoutView } from './ForceReadoutView'
import { s } from '../../core/schema'

/** A display node: the live force reading and F(r) chart of the force lab in the same experiment. */
export const forceReadoutModule = defineModule<'force-readout', null>({
  type: 'force-readout',
  label: 'Readout',
  about: {
    summary: 'Live force, distance and F(r) chart of the force lab with the same experimentId.',
    config: s.empty(),
  },
  width: 420,
  init: () => null,
  reduce: (state) => state,
  summarize: () => ({ shows: 'the force lab in the same experiment' }),
  View: ForceReadoutView,
})
