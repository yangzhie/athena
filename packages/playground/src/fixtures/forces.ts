import type { Scene } from '../contracts'

/**
 * TEST FIXTURE. Curve key points are what the agent would estimate once when
 * generating the scene (here: a Lennard-Jones fit for argon, ε ≈ 0.997 kJ/mol,
 * σ ≈ 0.3405 nm, checked by hand). Dragging interpolates between them locally.
 */
const curve = [
  [0.28, 1511.29], [0.29, 916.65], [0.3, 558.55], [0.31, 340.49], [0.32, 206.53], [0.33, 123.68],
  [0.34, 72.26], [0.35, 40.32], [0.36, 20.55], [0.37, 8.44], [0.38, 1.15], [0.39, -3.1], [0.4, -5.44],
  [0.42, -6.99], [0.45, -6.23], [0.5, -3.82], [0.55, -2.17], [0.6, -1.24], [0.7, -0.44], [0.8, -0.18],
  [0.9, -0.08], [1.0, -0.04], [1.1, -0.02], [1.2, -0.01],
].map(([r, f]) => ({ r, f }))

const moved: ('moveParticle' | 'setDistance')[] = ['moveParticle', 'setDistance']

export const forcesScene: Scene = {
  id: 'argon-balance',
  title: 'Chemistry · Intermolecular forces',
  goal: 'Find the distance where the force between two argon atoms balances',
  objects: [
    {
      id: 'question',
      type: 'note',
      title: 'The question',
      provenance: 'concept',
      config: {
        markdown:
          'Two argon atoms (Ar) share no chemical bond, only a weak van der Waals interaction.\n\nDrag either atom on the canvas to change the distance r, and watch whether the force **pulls** them together or **pushes** them apart. At what distance are they most “comfortable”?',
      },
    },
    {
      id: 'forces',
      type: 'force-lab',
      title: 'Two argon atoms',
      provenance: 'ai-estimate',
      experimentId: 'argon',
      near: 'question',
      config: {
        particles: [
          { label: 'Ar', color: '#0d9488', radius: 0.1 },
          { label: 'Ar', color: '#7c3aed', radius: 0.1 },
        ],
        curve,
        forceUnit: 'kJ/(mol·nm)',
        range: [0.28, 1.2],
        initialDistance: 0.9,
      },
    },
    {
      id: 'readout',
      type: 'force-readout',
      title: 'Force readout',
      provenance: 'ai-estimate',
      experimentId: 'argon',
      near: 'forces',
      config: {},
    },
  ],
  links: [
    { from: 'question', to: 'forces', relation: 'explains' },
    { from: 'forces', to: 'readout', relation: 'from' },
  ],
  checks: [
    {
      id: 'too-close',
      objectId: 'forces',
      on: moved,
      when: { field: 'distance', op: 'lt', value: 0.34 },
      verdict: 'misconception',
      explain: 'Closer is not always more attractive: here the electron clouds overlap and the atoms push each other apart hard.',
      respond: {
        say: 'A very common misconception: “the closer, the stronger the pull”. Up close the electron clouds overlap and repulsion shoots up (look at the red arrows). Watch my hand: I’ll pull the atoms into the attraction zone, then ease them in until the force is exactly zero.',
        calls: [{ name: 'demonstrate', input: { objectId: 'forces', actions: [{ type: 'setDistance', distance: 0.6 }, { type: 'setDistance', distance: 0.382 }] } }],
        then: {
          say: 'At about 0.38 nm attraction and repulsion cancel out. Try it yourself: nudge one atom slightly away from this spot. Which way do the arrows push it?',
          calls: [
            {
              name: 'add_object',
              input: {
                object: {
                  id: 'why-balance',
                  type: 'note',
                  title: 'Why closer isn’t better',
                  provenance: 'concept',
                  near: 'forces',
                  config: {
                    markdown:
                      'Far apart: fleeting dipoles cause a **weak attraction** that fades quickly with distance.\n\nVery close: the electron clouds overlap and **repulsion** grows steeply (much faster than attraction).\n\nWhere the two cancel is the equilibrium distance: the energy is lowest and the pair is most stable.',
                  },
                },
              },
            },
            { name: 'link', input: { from: 'why-balance', to: 'forces', relation: 'explains' } },
          ],
        },
      },
    },
    {
      id: 'close',
      objectId: 'forces',
      on: moved,
      when: { field: 'regime', op: 'eq', value: 'repulsive' },
      verdict: 'hint',
      explain: 'Still repulsion, but much weaker. Pull them apart a little more.',
    },
    {
      id: 'balanced',
      objectId: 'forces',
      on: moved,
      when: { field: 'regime', op: 'eq', value: 'balanced' },
      verdict: 'correct',
      explain: 'The net force is about zero: attraction and repulsion cancel. This is the equilibrium distance (about 0.38 nm).',
      completesGoal: true,
    },
    {
      id: 'attractive',
      objectId: 'forces',
      on: moved,
      when: { field: 'regime', op: 'eq', value: 'attractive' },
      verdict: 'hint',
      explain: 'This is attraction: let go and they would drift closer. Look nearer for the point where the force is zero.',
    },
    {
      id: 'too-far',
      objectId: 'forces',
      on: moved,
      when: { field: 'regime', op: 'eq', value: 'negligible' },
      verdict: 'hint',
      explain: 'Almost no force: they are too far apart to feel each other.',
    },
  ],
  intro: "Let's experiment. The two argon atoms are on the canvas: drag either one and watch the force arrows. Where do you think they settle?",
  showMe: {
    say: 'Watch my hand: from far apart the force goes from almost nothing to a pull, then to the point where pull and push cancel.',
    calls: [{ name: 'demonstrate', input: { objectId: 'forces', actions: [{ type: 'setDistance', distance: 0.6 }, { type: 'setDistance', distance: 0.382 }] } }],
    then: {
    say: 'At about 0.38 nm attraction and repulsion cancel out. Try it yourself: nudge one atom slightly away from this spot. Which way do the arrows push it?',
    calls: [
      {
        name: 'add_object',
        input: {
          object: {
            id: 'why-balance',
            type: 'note',
            title: 'Why closer isn’t better',
            provenance: 'concept',
            near: 'forces',
            config: {
              markdown:
                'Far apart: fleeting dipoles cause a **weak attraction** that fades quickly with distance.\n\nVery close: the electron clouds overlap and **repulsion** grows steeply (much faster than attraction).\n\nWhere the two cancel is the equilibrium distance: the energy is lowest and the pair is most stable.',
            },
          },
        },
      },
      { name: 'link', input: { from: 'why-balance', to: 'forces', relation: 'explains' } },
    ],
  },
  },
}
