import type { Scene, TutorResponse } from '../contracts'

const massNote: TutorResponse = {
  say: 'I’ve put the reason next to the pendulum.',
  calls: [
    {
      name: 'add_object',
      input: {
        object: {
          id: 'mass-note',
          type: 'note',
          title: 'Why the mass cancels',
          provenance: 'concept',
          near: 'note',
          side: 'below',
          config: {
            markdown:
              'A heavier bob is pulled harder (`mg`), but it is also harder to speed up (inertia `m`). The two cancel: the bob accelerates at `−(g/L)·x` whatever its mass.\n\nSo `T = 2π√(L/g)` has no mass in it, as long as the string is light and air drag is small.',
          },
        },
      },
    },
    { name: 'link', input: { from: 'mass-note', to: 'pendulum', relation: 'explains' } },
  ],
}

const lineNote: TutorResponse = {
  say: 'Here is why the plot is T² rather than T.',
  calls: [
    {
      name: 'add_object',
      input: {
        object: {
          id: 'line-note',
          type: 'note',
          title: 'Reading the line',
          provenance: 'concept',
          near: 'log',
          side: 'below',
          config: {
            markdown:
              'Squaring `T = 2π√(L/g)` gives `T² = (4π²/g)·L`: a straight line through the origin with slope 4π²/g, so g = 4π² / slope.\n\nThe formula assumes small swings (sin θ ≈ θ). The period grows with the release angle, about `T₀(1 + θ₀²/16)`: 2% longer at 30°, 7% at 60°. That is why large-angle points sit above the line.',
          },
        },
      },
    },
    { name: 'link', input: { from: 'line-note', to: 'log', relation: 'explains' } },
  ],
}

/**
 * TEST FIXTURE. A first-year mechanics lab: three separate pieces (pendulum,
 * photogate timer, log) connected by the student. The timer's data cable is
 * pre-plugged; clipping the photogate onto the pendulum is the student's job.
 * The pendulum's period includes the large-amplitude correction.
 */
export const pendulumScene: Scene = {
  id: 'pendulum-g',
  title: 'Physics lab · Simple pendulum',
  goal: 'Find g within 2% from T² against L',
  objects: [
    {
      id: 'note',
      type: 'note',
      title: 'Lab 2 · Measuring g',
      provenance: 'material',
      sources: [{ label: 'Sample material: Lab 2 · Simple pendulum' }],
      config: {
        markdown:
          'For small swings a pendulum’s period is `T = 2π√(L/g)`.\n\n1. Clip the **photogate** onto the bottom of the swing.\n\n2. Record T for at least **three lengths**, then **Fit g**: T² against L is a straight line with slope 4π²/g.\n\nWhile you’re at it: does a heavier bob swing faster?',
      },
    },
    { id: 'pendulum', type: 'pendulum', title: 'Pendulum', provenance: 'simulated', near: 'note', config: { g: 9.81 } },
    { id: 'timer', type: 'photogate', title: 'Timer', provenance: 'simulated', near: 'pendulum', config: {} },
    { id: 'log', type: 'pendulum-log', title: 'Periods', provenance: 'simulated', near: 'timer', config: {} },
  ],
  links: [{ from: 'note', to: 'pendulum', relation: 'explains' }],
  wiring: [{ plug: { objectId: 'timer', port: 'data' }, to: { objectId: 'log', port: 'in' } }],
  checks: [
    // Recording a period
    {
      id: 'record-no-timer',
      objectId: 'log',
      on: ['recordPeriod'],
      when: { field: 'connected', op: 'eq', value: false },
      verdict: 'hint',
      explain: "Plug the timer's data cable into the log first.",
    },
    {
      id: 'record-no-gate',
      objectId: 'log',
      on: ['recordPeriod'],
      when: { field: 'gated', op: 'eq', value: false },
      verdict: 'hint',
      explain: 'The timer has nothing to time: clip the photogate onto the bottom of the swing.',
    },
    {
      id: 'record-same-other-mass',
      objectId: 'log',
      on: ['recordPeriod'],
      when: { field: 'sameOtherMass', op: 'eq', value: true },
      verdict: 'correct',
      explain: 'Same length, different mass, same period: the mass doesn’t matter.',
      respond: {
        say: 'Same period with a different bob. A heavier bob feels a bigger pull, but it is just as much harder to get moving, so the two cancel.',
        calls: massNote.calls,
      },
    },
    {
      id: 'record-large-angle',
      objectId: 'log',
      on: ['recordPeriod'],
      when: { field: 'amplitude', op: 'gt', value: 15 },
      verdict: 'misconception',
      explain: 'Released this wide, the period is longer than 2π√(L/g), so this point will pull g down.',
      respond: {
        say: '`T = 2π√(L/g)` only holds for small swings, where sin θ ≈ θ. At 30° the period is about 2% longer, at 60° about 7%, and that error goes straight into g. Pull the bob out less than 10° and retake this length; it replaces the row.',
        calls: [{ name: 'highlight', input: { objectId: 'pendulum', part: 'bob', note: 'Pull it out less: under 10°' } }],
      },
    },
    {
      id: 'record-ok',
      objectId: 'log',
      on: ['recordPeriod'],
      when: { field: 'amplitude', op: 'lte', value: 15 },
      verdict: 'hint',
      explain: 'Recorded. Use at least three lengths spread between 0.2 and 1.5 m, then fit g.',
    },
    // Fitting
    {
      id: 'fit-few',
      objectId: 'log',
      on: ['fitG'],
      when: { field: 'points', op: 'lt', value: 3 },
      verdict: 'hint',
      explain: 'Use at least three different lengths, so you can see the points really lie on a line.',
    },
    {
      id: 'fit-large-angle',
      objectId: 'log',
      on: ['fitG'],
      when: { field: 'largeAngle', op: 'eq', value: true },
      verdict: 'hint',
      explain: 'Some points (orange) were released above 15°, where the period runs long and g comes out low. Retake them at a small angle.',
    },
    {
      id: 'fit-off',
      objectId: 'log',
      on: ['fitG'],
      when: { field: 'gErrorPct', op: 'gt', value: 2 },
      verdict: 'hint',
      explain: 'g is more than 2% from 9.81 m/s². Spread the lengths out more and check every point is from a small swing.',
    },
    {
      id: 'fit-good',
      objectId: 'log',
      on: ['fitG'],
      when: { field: 'gErrorPct', op: 'lte', value: 2 },
      verdict: 'correct',
      explain: 'g within 2% of 9.81 m/s², from small swings at three or more lengths.',
      completesGoal: true,
      respond: { say: '🎉 You’ve measured g.', calls: lineNote.calls },
    },
  ],
  intro:
    'Let’s measure it. Drag the photogate plug onto the bottom of the swing, pull the bob out a little, and record T in the log. Drag the pivot to change the length, and try a different bob from the base along the way.',
  showMe: {
    say: 'Watch my hand: photogate on the bottom of the swing, a small 5° release, then T at three lengths and a straight-line fit of T² against L.',
    calls: [
      {
        name: 'demonstrate',
        input: {
          objectId: 'pendulum',
          actions: [
            { objectId: 'timer', type: 'connect', plug: 'gate', to: { objectId: 'pendulum', port: 'gate' } },
            { type: 'setAmplitude', degrees: 5 },
            { type: 'setLength', metres: 0.4 },
            { objectId: 'log', type: 'recordPeriod' },
            { type: 'setLength', metres: 0.8 },
            { objectId: 'log', type: 'recordPeriod' },
            { type: 'setLength', metres: 1.2 },
            { objectId: 'log', type: 'recordPeriod' },
            { objectId: 'log', type: 'fitG' },
          ],
        },
      },
    ],
    then: lineNote,
  },
}
