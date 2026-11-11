import type { ObjectAction, Scene, TutorResponse } from '../contracts'

/** Good technique: run in fast, then drop by drop with a swirl after each step, then record. */
const technique: ObjectAction[] = [
  { type: 'newTrial' },
  { type: 'dispenseTo', volume: 21, mode: 'stream' },
  { type: 'swirl' },
  { type: 'dispenseTo', volume: 22.6, mode: 'dropwise' },
  { type: 'swirl' },
  { type: 'dispenseTo', volume: 22.95, mode: 'dropwise' },
  { type: 'swirl' },
  { type: 'dispenseTo', volume: 23.05, mode: 'dropwise' },
  { type: 'swirl' },
  { type: 'recordEndpoint' },
]

const endpointNote: TutorResponse = {
  say: 'My titre is in the trials table. Work out c(NaOH) = 0.100 × 25.00 ÷ titre, then press New trial and aim for a titre within 0.10 mL of mine.',
  calls: [
    {
      name: 'add_object',
      input: {
        object: {
          id: 'endpoint-note',
          type: 'note',
          title: 'Endpoint vs equivalence point',
          provenance: 'concept',
          near: 'procedure',
          config: {
            markdown:
              'The **equivalence point** is where moles of NaOH equal moles of HCl (pH 7 here).\n\nThe **endpoint** is where the indicator changes colour. Phenolphthalein turns pink from about pH 8.2, which this titration passes within one drop of equivalence, so the endpoint is a good stand-in.\n\nThat is also why one extra drop matters: past equivalence, every drop goes straight into excess base.',
          },
        },
      },
    },
    { name: 'link', input: { from: 'endpoint-note', to: 'rig', relation: 'explains' } },
  ],
}

/**
 * TEST FIXTURE. A first-year lab: standardise a sodium hydroxide solution
 * against a standard hydrochloric acid solution with phenolphthalein. The
 * "true" NaOH concentration is what the agent would pick when generating the
 * scene; the student finds it from their titre.
 */
export const titrationScene: Scene = {
  id: 'naoh-standardisation',
  title: 'Chemistry lab · Acid–base titration',
  goal: 'Find the endpoint titre of NaOH against 25.00 mL of 0.100 M HCl, and from it the NaOH concentration',
  objects: [
    {
      id: 'procedure',
      type: 'note',
      title: 'Lab 4 · Standardising NaOH',
      provenance: 'concept',
      config: {
        markdown:
          'The flask holds **25.00 mL of 0.100 M HCl** with a few drops of phenolphthalein. The burette holds NaOH of roughly 0.1 M; your job is to find its exact concentration.\n\n1. Open the tap and run in NaOH, **swirling** the flask as you go (shake it sideways).\n\n2. When pink flashes start to linger, close down to **dropwise** and swirl after every drop.\n\n3. The **endpoint** is the first faint pink that stays after swirling. Record the burette reading.\n\n4. Repeat until two titres agree within 0.10 mL. NaOH + HCl → NaCl + H₂O, so c(NaOH) = 0.100 × 25.00 ÷ titre.',
      },
    },
    {
      id: 'rig',
      type: 'titration',
      title: 'Titration rig',
      provenance: 'simulated',
      experimentId: 'titration',
      near: 'procedure',
      config: {
        analyte: { formula: 'HCl', concentration: 0.1, volume: 25 },
        titrant: { formula: 'NaOH', concentration: 0.1087, label: 'NaOH (≈ 0.1 M, to standardise)' },
        indicator: { name: 'phenolphthalein', transition: [8.2, 10] },
        burette: { capacity: 50, dropVolume: 0.05 },
      },
    },
    {
      id: 'lab-readout',
      type: 'titration-readout',
      title: 'Lab readout',
      provenance: 'simulated',
      experimentId: 'titration',
      near: 'rig',
      config: {},
    },
  ],
  links: [
    { from: 'procedure', to: 'rig', relation: 'explains' },
    { from: 'rig', to: 'lab-readout', relation: 'from' },
  ],
  checks: [
    // Turning the tap
    {
      id: 'stream-near-endpoint',
      objectId: 'rig',
      on: ['setTap'],
      when: { all: [{ field: 'flow', op: 'eq', value: 'stream' }, { field: 'nearEndpoint', op: 'eq', value: true }] },
      verdict: 'hint',
      explain: 'The pink is starting to linger, so you are close. Turn the tap down to dropwise and swirl after every drop.',
    },
    { id: 'tap', objectId: 'rig', on: ['setTap'], when: { field: 'volume', op: 'gte', value: 0 }, verdict: 'hint', explain: '', silent: true },
    // Swirling
    {
      id: 'swirl-deep',
      objectId: 'rig',
      on: ['swirl'],
      when: { field: 'colour', op: 'eq', value: 'deep pink' },
      verdict: 'hint',
      explain: 'Deep pink that stays: there is already excess NaOH, so this flask is past the endpoint.',
    },
    {
      id: 'swirl-faint',
      objectId: 'rig',
      on: ['swirl'],
      when: { field: 'colour', op: 'eq', value: 'faint pink' },
      verdict: 'hint',
      explain: 'A faint pink that stays after swirling: this is the endpoint. Record the burette reading.',
    },
    { id: 'swirl', objectId: 'rig', on: ['swirl'], when: { field: 'colour', op: 'eq', value: 'colourless' }, verdict: 'hint', explain: '', silent: true },
    // Recording
    {
      id: 'record-unmixed',
      objectId: 'rig',
      on: ['recordEndpoint'],
      when: { field: 'mixed', op: 'eq', value: false },
      verdict: 'misconception',
      explain: 'That pink was only where the drops landed. Swirl first: if it fades, you are not at the endpoint yet.',
      respond: {
        say: 'Easy to fall for: a drop of NaOH turns the spot where it lands pink for a moment, before it meets the acid in the rest of the flask. That flash is not the endpoint. Watch: I swirl, and the pink fades because there is still acid left.',
        calls: [{ name: 'demonstrate', input: { objectId: 'rig', actions: [{ type: 'swirl' }] } }],
        once: false,
      },
    },
    {
      id: 'record-colourless',
      objectId: 'rig',
      on: ['recordEndpoint'],
      when: { field: 'colour', op: 'eq', value: 'colourless' },
      verdict: 'hint',
      explain: 'The flask is still colourless after swirling: there is no excess base yet. Keep adding.',
    },
    {
      id: 'record-overshoot',
      objectId: 'rig',
      on: ['recordEndpoint'],
      when: { field: 'overshoot', op: 'gt', value: 0.15 },
      verdict: 'misconception',
      explain: 'Overshot: deep pink means excess NaOH, so this titre is too large and the concentration you calculate will be too low.',
      respond: {
        say: 'This one ran past the endpoint. Near the end a single drop is enough to turn the whole flask pink, and a running tap delivers several drops a second, so the titre comes out too large and c(NaOH) too low. Want to see the technique on a fresh flask? Accept the suggestion under the rig and I’ll run a full trial.',
        calls: [{ name: 'demonstrate', input: { objectId: 'rig', actions: technique } }],
        once: false,
        then: endpointNote,
      },
    },
    {
      id: 'record-good',
      objectId: 'rig',
      on: ['recordEndpoint'],
      when: { field: 'overshoot', op: 'between', value: [-0.05, 0.15] },
      verdict: 'correct',
      explain: 'Good endpoint: within a drop or two of equivalence. Now calculate c(NaOH) and repeat for a concordant titre.',
      completesGoal: true,
    },
  ],
  intro:
    "Let's practise on the bench. The burette, flask and readout are on the Playground. Turn the tap to run in NaOH, shake the flask sideways to swirl, and record the burette reading when you think you've hit the endpoint.",
  showMe: {
    say: 'Here is the technique: run in fast to about 2 mL before the endpoint, then dropwise, swirling after each step, and record at the first faint pink that stays.',
    calls: [{ name: 'demonstrate', input: { objectId: 'rig', actions: technique } }],
    then: endpointNote,
  },
}
