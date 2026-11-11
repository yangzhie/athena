import type { Scene, TutorResponse } from '../contracts'

const intensityNote: TutorResponse = {
  say: 'I’ve put the reason next to the rig. Keep it in mind when you choose which readings go into your fit.',
  calls: [
    {
      name: 'add_object',
      input: {
        object: {
          id: 'intensity-note',
          type: 'note',
          title: 'Intensity or frequency?',
          provenance: 'concept',
          near: 'rig',
          side: 'below',
          config: {
            markdown:
              'Brighter light means **more photons per second**, so more electrons leave the cathode and the current rises.\n\nEach electron absorbs **one** photon, so the most energy it can leave with is `hf − φ`. That depends only on the frequency, which is why V₀ didn’t move.',
          },
        },
      },
    },
    { name: 'link', input: { from: 'intensity-note', to: 'rig', relation: 'explains' } },
  ],
}

const einsteinNote: TutorResponse = {
  say: 'Here is what each part of your line means.',
  calls: [
    {
      name: 'add_object',
      input: {
        object: {
          id: 'einstein-note',
          type: 'note',
          title: 'Reading the line',
          provenance: 'concept',
          near: 'log',
          side: 'below',
          config: {
            markdown:
              'Einstein’s equation: `eV₀ = hf − φ`.\n\nThe **slope** is h/e, the same for every metal. The **intercept** is −φ/e, so it depends on the cathode.\n\nWhere the line meets the frequency axis is the **threshold frequency** f₀ = φ/h. Below it there is no current at any intensity, which is what the green and yellow lines showed.',
          },
        },
      },
    },
    { name: 'link', input: { from: 'einstein-note', to: 'log', relation: 'explains' } },
  ],
}

/**
 * TEST FIXTURE. A first-year modern physics lab: find Planck's constant from
 * stopping voltages. Potassium (φ ≈ 2.30 eV) puts the threshold at about
 * 541 nm, so the mercury UV, violet and blue lines free electrons and the
 * green and yellow lines don't. Their V₀ are 1.097, 0.764 and 0.545 V.
 */
export const photoelectricScene: Scene = {
  id: 'photoelectric-planck',
  title: 'Physics lab · Photoelectric effect',
  goal: 'Measure the stopping voltage for each lamp line and find Planck’s constant within 5%',
  objects: [
    {
      id: 'question',
      type: 'note',
      title: 'Lab 7 · Planck’s constant',
      provenance: 'material',
      sources: [{ label: 'Sample material: Lab 7 · Photoelectric effect' }],
      config: {
        markdown:
          'Light frees electrons from a **potassium** cathode. A retarding voltage pushes them back; at the **stopping voltage V₀** even the fastest no longer reach the anode, and the current is zero.\n\n1. For each lamp line, raise the voltage until the meter first reads **0.0 nA**, then record V₀.\n\n2. Fit V₀ against frequency. Since `eV₀ = hf − φ`, the slope gives **h**.',
      },
    },
    {
      id: 'predict',
      type: 'predict',
      title: 'Before you measure',
      provenance: 'concept',
      near: 'question',
      side: 'below',
      config: {
        question: 'If you make the UV light four times brighter, the stopping voltage V₀ will…',
        options: ['increase', 'stay the same', 'decrease'],
      },
    },
    {
      id: 'rig',
      type: 'photoelectric',
      title: 'Phototube',
      provenance: 'simulated',
      near: 'question',
      config: {
        cathode: { label: 'Potassium', workFunction: 2.3 },
        lines: [
          { label: 'UV', wavelength: 365.0 },
          { label: 'Violet', wavelength: 404.7 },
          { label: 'Blue', wavelength: 435.8 },
          { label: 'Green', wavelength: 546.1 },
          { label: 'Yellow', wavelength: 577.0 },
        ],
        maxCurrent: 40,
      },
    },
    { id: 'log', type: 'photo-log', title: 'Stopping voltages', provenance: 'simulated', near: 'rig', config: {} },
  ],
  links: [
    { from: 'question', to: 'rig', relation: 'explains' },
    { from: 'predict', to: 'rig', relation: 'explains' },
  ],
  wiring: [{ plug: { objectId: 'rig', port: 'data' }, to: { objectId: 'log', port: 'in' } }],
  checks: [
    // The prediction
    {
      id: 'predict-increase',
      objectId: 'predict',
      on: ['choose'],
      when: { field: 'choice', op: 'eq', value: 0 },
      verdict: 'misconception',
      explain: 'Most people expect this: brighter light carries more energy, so the electrons should be faster. Test it.',
      respond: {
        say: 'That’s the classical prediction, and the one this experiment was famous for breaking. Test it yourself: record V₀ for the UV line with the lamp pulled far back, then again with it close up. Watch both the current and the voltage where it reaches zero.',
        calls: [{ name: 'highlight', input: { objectId: 'rig', part: 'lamp', note: 'Slide the lamp back, then close' } }],
      },
    },
    {
      id: 'predict-decrease',
      objectId: 'predict',
      on: ['choose'],
      when: { field: 'choice', op: 'eq', value: 2 },
      verdict: 'misconception',
      explain: 'Brighter light doesn’t make each electron slower. Test it.',
      respond: {
        say: 'Interesting guess. Test it: record V₀ for the UV line with the lamp far back, then again close up, and compare.',
        calls: [{ name: 'highlight', input: { objectId: 'rig', part: 'lamp', note: 'Slide the lamp back, then close' } }],
      },
    },
    {
      id: 'predict-same',
      objectId: 'predict',
      on: ['choose'],
      when: { field: 'choice', op: 'eq', value: 1 },
      verdict: 'correct',
      explain: 'Good prediction. Check it: record the UV line with the lamp at two distances.',
    },
    // The rig
    {
      id: 'brighter-below-threshold',
      objectId: 'rig',
      on: ['setIntensity'],
      when: { all: [{ field: 'belowThreshold', op: 'eq', value: true }, { field: 'intensity', op: 'gte', value: 0.95 }] },
      verdict: 'misconception',
      explain: 'Still no current with the lamp right up close: below the threshold frequency, brighter light frees no electrons.',
      respond: {
        say: 'No electrons, however bright. Each photon of this light carries less energy than the 2.30 eV needed to free an electron from potassium, and an electron can’t collect energy from two photons. Only light of a higher frequency (a shorter wavelength) frees them.',
        calls: [{ name: 'highlight', input: { objectId: 'rig', note: 'Below the threshold frequency' } }],
      },
    },
    {
      id: 'line-below-threshold',
      objectId: 'rig',
      on: ['selectLine', 'setIntensity'],
      when: { field: 'belowThreshold', op: 'eq', value: true },
      verdict: 'hint',
      explain: 'No current even at 0 V: this light frees no electrons from the cathode.',
    },
    { id: 'rig-other', objectId: 'rig', on: ['selectLine', 'setIntensity'], when: { field: 'current', op: 'gte', value: 0 }, verdict: 'hint', explain: '', silent: true },
    // Recording V₀
    {
      id: 'record-no-rig',
      objectId: 'log',
      on: ['recordStop'],
      when: { field: 'connected', op: 'eq', value: false },
      verdict: 'hint',
      explain: "Plug the rig's data cable into the log first.",
    },
    {
      id: 'record-below-threshold',
      objectId: 'log',
      on: ['recordStop'],
      when: { field: 'belowThreshold', op: 'eq', value: true },
      verdict: 'hint',
      explain: 'No electrons with this light, so there is no V₀ to record: it is below the threshold frequency.',
    },
    {
      id: 'record-current',
      objectId: 'log',
      on: ['recordStop'],
      when: { field: 'current', op: 'gt', value: 0 },
      verdict: 'hint',
      explain: 'The meter still shows a current, so some electrons still reach the anode. Raise the voltage until it reads 0.0 nA.',
    },
    {
      id: 'record-past',
      objectId: 'log',
      on: ['recordStop'],
      when: { field: 'overshoot', op: 'gt', value: 0.05 },
      verdict: 'hint',
      explain: 'Recorded, but the current was already zero at a lower voltage. Come back down to where it first reads 0.0 nA and record again; it replaces this one.',
    },
    {
      id: 'record-same-at-other-intensity',
      objectId: 'log',
      on: ['recordStop'],
      when: { field: 'repeatSame', op: 'eq', value: true },
      verdict: 'correct',
      explain: 'Same V₀ at a different intensity: the current changed, the electrons’ maximum energy didn’t.',
      respond: {
        say: 'There it is: a different intensity, a different current, and the same V₀. Brighter light frees more electrons, but not faster ones. That is what classical wave theory couldn’t explain.',
        calls: intensityNote.calls,
      },
    },
    {
      id: 'record-ok',
      objectId: 'log',
      on: ['recordStop'],
      when: { field: 'overshoot', op: 'lte', value: 0.05 },
      verdict: 'hint',
      explain: 'Recorded. Measure V₀ for every line that gives a current, then fit the line.',
    },
    // Fitting
    {
      id: 'fit-few',
      objectId: 'log',
      on: ['fitLine'],
      when: { field: 'points', op: 'lt', value: 2 },
      verdict: 'hint',
      explain: 'A line needs V₀ for at least two different lines, and three are better.',
    },
    {
      id: 'fit-two',
      objectId: 'log',
      on: ['fitLine'],
      when: { field: 'points', op: 'eq', value: 2 },
      verdict: 'hint',
      explain: 'A line through two points always fits. Add the third line that gives a current, to check the points really lie on a line.',
    },
    {
      id: 'fit-off',
      objectId: 'log',
      on: ['fitLine'],
      when: { field: 'errorPct', op: 'gt', value: 5 },
      verdict: 'hint',
      explain: 'h is more than 5% off. Look for a V₀ recorded well past the voltage where the current first reached zero.',
    },
    {
      id: 'fit-good',
      objectId: 'log',
      on: ['fitLine'],
      when: { field: 'errorPct', op: 'lte', value: 5 },
      verdict: 'correct',
      explain: 'h within 5% of 6.63 × 10⁻³⁴ J·s, from three stopping voltages.',
      completesGoal: true,
      respond: { say: '🎉 You’ve measured Planck’s constant. Here is what each part of your line means.', calls: einsteinNote.calls },
    },
  ],
  intro:
    'Let’s run it. Answer the prediction first. Then slide the selector along the spectrum to pick a lamp line, turn the voltage knob up until the current first reaches 0.0 nA, and record V₀ in the log on the right. Sliding the lamp closer makes the light brighter.',
  showMe: {
    say: 'Watch my hand: for each line that gives a current I turn the knob just until the meter reads 0.0 nA and record it, then fit V₀ against frequency.',
    calls: [
      {
        name: 'demonstrate',
        input: {
          objectId: 'rig',
          actions: [
            { type: 'selectLine', index: 0 },
            { type: 'setIntensity', level: 1 },
            { type: 'setVoltage', volts: 1.1 },
            { objectId: 'log', type: 'recordStop' },
            { type: 'selectLine', index: 1 },
            { type: 'setVoltage', volts: 0.77 },
            { objectId: 'log', type: 'recordStop' },
            { type: 'selectLine', index: 2 },
            { type: 'setVoltage', volts: 0.55 },
            { objectId: 'log', type: 'recordStop' },
            { objectId: 'log', type: 'fitLine' },
          ],
        },
      },
    ],
    then: einsteinNote,
  },
}
