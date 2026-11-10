import type { ObjectSpec, Scene } from '../contracts'

/**
 * TEST FIXTURE. A first-year electrochemistry lab: build a Daniell cell from
 * separate pieces of apparatus, measure its potential, then reuse the same
 * meter and salt bridge with a new half-cell. Each piece is an independent
 * component; the student connects them by dragging leads and tube ends.
 */
export const silverHalfCell: ObjectSpec = {
  id: 'cell-ag',
  type: 'half-cell',
  title: 'Ag | Ag⁺',
  provenance: 'simulated',
  near: 'cell-cu',
  side: 'below',
  config: { metal: 'Ag', ion: 'Ag⁺', electrons: 1, standardPotential: 0.8, concentration: 1, solutionColor: '#cbd5e1' },
}

export const galvanicScene: Scene = {
  id: 'galvanic-cells',
  title: 'Chemistry lab · Galvanic cells',
  goal: 'Build a Zn | Cu cell, measure its potential and find out which electrode is the anode',
  objects: [
    {
      id: 'procedure',
      type: 'note',
      title: 'Lab 6 · Galvanic cells',
      provenance: 'concept',
      config: {
        markdown:
          'Each beaker is a **half-cell**: a metal in a 1.00 M solution of its ions.\n\n1. Dip one end of the **salt bridge** into each beaker (drag the tube ends).\n\n2. Clip the voltmeter **red (V)** and **black (COM)** leads onto the two electrodes.\n\n3. Record the reading. A positive reading means the red lead is on the **cathode**, where reduction happens.\n\n4. Explore: dilute a solution and record again.\n\nE° (V): Zn²⁺/Zn −0.76 · Cu²⁺/Cu +0.34 · Ag⁺/Ag +0.80',
      },
    },
    { id: 'voltmeter', type: 'voltmeter', title: 'Voltmeter', provenance: 'simulated', near: 'procedure', config: {} },
    {
      id: 'cell-zn',
      type: 'half-cell',
      title: 'Zn | Zn²⁺',
      provenance: 'simulated',
      near: 'voltmeter',
      side: 'below',
      config: { metal: 'Zn', ion: 'Zn²⁺', electrons: 2, standardPotential: -0.762, concentration: 1, solutionColor: '#bae6fd' },
    },
    { id: 'bridge', type: 'salt-bridge', title: 'Salt bridge', provenance: 'simulated', near: 'cell-zn', config: { electrolyte: 'KNO₃' } },
    {
      id: 'cell-cu',
      type: 'half-cell',
      title: 'Cu | Cu²⁺',
      provenance: 'simulated',
      near: 'bridge',
      config: { metal: 'Cu', ion: 'Cu²⁺', electrons: 2, standardPotential: 0.34, concentration: 1, solutionColor: '#2563eb' },
    },
    { id: 'log', type: 'potential-log', title: 'Cell potentials', provenance: 'simulated', near: 'cell-cu', config: {} },
  ],
  links: [{ from: 'procedure', to: 'voltmeter', relation: 'explains' }],
  wiring: [{ plug: { objectId: 'voltmeter', port: 'data' }, to: { objectId: 'log', port: 'in' } }],
  checks: [
    {
      id: 'bridge-same-beaker',
      objectId: 'bridge',
      on: ['connect'],
      when: { field: 'sameBeaker', op: 'eq', value: true },
      verdict: 'hint',
      explain: 'Both ends are in the same beaker. The bridge has to join the two solutions.',
    },
    { id: 'bridge-joined', objectId: 'bridge', on: ['connect'], when: { field: 'sameBeaker', op: 'eq', value: false }, verdict: 'hint', explain: '', silent: true },
    // Recording a reading
    {
      id: 'record-no-meter',
      objectId: 'log',
      on: ['recordReading'],
      when: { field: 'connected', op: 'eq', value: false },
      verdict: 'hint',
      explain: "Plug the voltmeter's data cable into the notebook first.",
    },
    {
      id: 'record-unplugged',
      objectId: 'log',
      on: ['recordReading'],
      when: { field: 'circuit', op: 'eq', value: 'unplugged' },
      verdict: 'hint',
      explain: 'Clip both voltmeter leads onto electrodes, one in each beaker, before recording.',
    },
    {
      id: 'record-same-cell',
      objectId: 'log',
      on: ['recordReading'],
      when: { field: 'circuit', op: 'eq', value: 'same-cell' },
      verdict: 'hint',
      explain: 'Both leads are on the same electrode, so there is no potential difference to measure.',
    },
    {
      id: 'record-open',
      objectId: 'log',
      on: ['recordReading'],
      when: { field: 'circuit', op: 'eq', value: 'open' },
      verdict: 'misconception',
      explain: '0.000 V: electrons could travel through the leads, but no ions can move between the beakers, so no charge flows. The circuit is not complete.',
      respond: {
        say: 'The leads let electrons travel between the metals, but the two solutions are not connected, so ions cannot move to balance the charge. Without that, no current flows and the meter reads 0. Watch: I dip the salt bridge into both beakers and record again.',
        calls: [
          {
            name: 'demonstrate',
            input: {
              objectId: 'bridge',
              actions: [
                { type: 'connect', plug: 'a', to: { objectId: 'cell-zn', port: 'solution' } },
                { type: 'connect', plug: 'b', to: { objectId: 'cell-cu', port: 'solution' } },
                { objectId: 'log', type: 'recordReading' },
              ],
            },
          },
        ],
      },
    },
    {
      id: 'record-reversed',
      objectId: 'log',
      on: ['recordReading'],
      when: { field: 'volts', op: 'lt', value: 0 },
      verdict: 'misconception',
      explain: 'A negative reading means the leads are swapped, not that the cell runs backwards. The red lead belongs on the cathode.',
      respond: {
        say: 'The cell is fine; the meter only reports red minus black. A negative number tells you the red lead sits on the anode. Swap the leads so red is on the electrode where reduction happens. I’ll do it once.',
        calls: [
          { name: 'highlight', input: { objectId: 'voltmeter', note: 'Red (V) goes on the cathode' } },
          {
            name: 'demonstrate',
            input: { objectId: 'voltmeter', actions: [{ type: 'swapPlugs', plugs: ['v', 'com'] }, { objectId: 'log', type: 'recordReading' }] },
          },
        ],
      },
    },
    {
      id: 'record-zn-cu',
      objectId: 'log',
      on: ['recordReading'],
      when: { all: [{ field: 'pair', op: 'eq', value: 'Cu|Zn' }, { field: 'standard', op: 'eq', value: true }] },
      verdict: 'correct',
      explain: '+1.10 V with red on Cu: Cu is the cathode (Cu²⁺ is reduced) and Zn the anode (Zn is oxidised). E°cell = 0.34 − (−0.76) = 1.10 V.',
      completesGoal: true,
      respond: {
        say: '🎉 That’s the Daniell cell: zinc is oxidised at the anode, Cu²⁺ is reduced at the cathode. I’ve added a silver half-cell to the bench. Before you measure: in a Cu | Ag cell, which electrode is the cathode now, and what will the meter read? Move the bridge end and the leads to find out.',
        calls: [{ name: 'add_object', input: { object: silverHalfCell } }],
      },
    },
    {
      id: 'record-ag-cu',
      objectId: 'log',
      on: ['recordReading'],
      when: { all: [{ field: 'pair', op: 'eq', value: 'Ag|Cu' }, { field: 'standard', op: 'eq', value: true }] },
      verdict: 'correct',
      explain: '+0.46 V with red on Ag: now Cu is the anode. Whether an electrode is the anode depends on its partner.',
    },
    {
      id: 'record-nonstandard',
      objectId: 'log',
      on: ['recordReading'],
      when: { field: 'standard', op: 'eq', value: false },
      verdict: 'hint',
      explain: 'Compare with your 1.00 M reading. Diluting the cathode solution lowers E; diluting the anode solution raises it (Nernst: 0.059/n V per tenfold change, where n is the number of electrons).',
    },
    { id: 'record-other', objectId: 'log', on: ['recordReading'], when: { field: 'volts', op: 'gt', value: 0 }, verdict: 'correct', explain: 'Recorded.' },
  ],
  intro:
    "Let's build one. The bench has two half-cells, a salt bridge, a voltmeter and your notebook, each a separate piece. Drag the tube ends of the salt bridge into the beakers and the meter's leads onto the electrodes, then record the reading. Try it without the bridge too, if you like.",
  showMe: {
    say: 'Watch my hand: salt bridge into both beakers, red lead on copper (the cathode), black lead on zinc (the anode), then record.',
    calls: [
      {
        name: 'demonstrate',
        input: {
          objectId: 'bridge',
          actions: [
            { type: 'connect', plug: 'a', to: { objectId: 'cell-zn', port: 'solution' } },
            { type: 'connect', plug: 'b', to: { objectId: 'cell-cu', port: 'solution' } },
            { objectId: 'voltmeter', type: 'connect', plug: 'v', to: { objectId: 'cell-cu', port: 'electrode' } },
            { objectId: 'voltmeter', type: 'connect', plug: 'com', to: { objectId: 'cell-zn', port: 'electrode' } },
            { objectId: 'log', type: 'recordReading' },
          ],
        },
      },
    ],
  },
}
