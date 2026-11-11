import type { ObjectAction, Scene, TutorResponse } from '../contracts'

const values = [5, 1, 4, 2, 8]

/** Bubble sort with early exit, as bench actions: start over, decide every pair, then stop. */
function trace(start: number[]): ObjectAction[] {
  const a = [...start]
  const steps: ObjectAction[] = [{ type: 'resetSort' }]
  for (let end = a.length - 1; end > 0; end--) {
    let swapped = false
    for (let j = 0; j < end; j++) {
      if (a[j] > a[j + 1]) {
        ;[a[j], a[j + 1]] = [a[j + 1], a[j]]
        swapped = true
        steps.push({ type: 'swap', index: j })
      } else steps.push({ type: 'keep', index: j })
    }
    if (!swapped) break
  }
  return [...steps, { type: 'finish' }]
}

const counts: TutorResponse = {
  say: "I've pinned what early exit buys here. On a list that's already sorted it stops after one pass; on a reversed one it runs every pass, which is why the worst case stays O(n²).",
  calls: [
    {
      name: 'add_object',
      input: {
        object: {
          id: 'pass-counts',
          type: 'result',
          title: 'Comparisons for five values',
          provenance: 'concept',
          near: 'bench',
          config: {
            rows: [
              { label: 'With early exit', value: '9', note: '3 passes: stops after one with no swaps' },
              { label: 'Without early exit', value: '10', note: '4 passes: n(n−1)/2 for n = 5' },
              { label: 'Already sorted', value: '4', note: '1 pass: best case, O(n)' },
            ],
            caption: 'Counts for [5, 1, 4, 2, 8] and its sorted order.',
          },
        },
      },
    },
    { name: 'link', input: { from: 'bench', to: 'pass-counts', relation: 'from' } },
  ],
}

const onePassNote: TutorResponse = {
  say: 'Pass 1 only carried 5 one step at a time until 8 stopped it; 2 still needed another pass to move left. Notice the swaps column: the trace stops once a pass makes none.',
  calls: [
    {
      name: 'add_object',
      input: {
        object: {
          id: 'why-passes',
          type: 'note',
          title: 'Why one pass isn’t enough',
          provenance: 'concept',
          near: 'bench',
          config: {
            markdown:
              'A pass guarantees one thing: the **largest** value left reaches the end. That is why the green part grows by one each pass.\n\nA small value near the end moves left only **one step per pass**, so it can take many passes to arrive.\n\nThe algorithm can stop after a pass with **no swaps**: every neighbouring pair was in order, so the whole list is.',
          },
        },
      },
    },
    { name: 'link', input: { from: 'why-passes', to: 'bench', relation: 'explains' } },
  ],
}

/**
 * TEST FIXTURE. A hand-written scene standing in for what the agent would
 * generate from the unit's material and the student's question.
 */
export const bubbleScene: Scene = {
  id: 'bubble-sort',
  title: 'Algorithms · Bubble sort',
  goal: 'Sort [5, 1, 4, 2, 8] with bubble sort and stop as soon as the algorithm can know it is done',
  objects: [
    {
      id: 'question',
      type: 'note',
      title: 'The question',
      provenance: 'material',
      sources: [{ label: 'Sample material: bubble_sort.py' }],
      config: {
        markdown:
          'Trace **bubble sort** on `[5, 1, 4, 2, 8]` by hand.\n\nIn the highlighted pair, if the left value is bigger, **drag it past** its neighbour to swap them; otherwise **slide the arrow on** to keep them. Each pass carries the largest value left to the end. The code next to the bench follows your trace.\n\nIt stops early with `if not swapped: break`. When can you press **Done**?',
      },
    },
    {
      id: 'bench',
      type: 'sort-bench',
      title: 'Bubble sort',
      provenance: 'material',
      near: 'question',
      sources: [{ label: 'Sample material: bubble_sort.py' }],
      experimentId: 'bubble',
      config: { algorithm: 'bubble', values },
    },
    {
      id: 'code',
      type: 'sort-code',
      title: 'bubble_sort.py',
      provenance: 'material',
      near: 'bench',
      experimentId: 'bubble',
      sources: [{ label: 'Sample material: bubble_sort.py' }],
      config: {
        language: 'python',
        source: [
          'def bubble_sort(a):',
          '    n = len(a)',
          '    for i in range(n - 1):',
          '        swapped = False',
          '        for j in range(n - 1 - i):',
          '            if a[j] > a[j + 1]:',
          '                a[j], a[j + 1] = a[j + 1], a[j]',
          '                swapped = True',
          '        if not swapped:',
          '            break',
          '    return a',
        ].join('\n'),
        lines: { compare: 6, swap: 7, passEnd: 9, stop: 10 },
      },
    },
  ],
  links: [
    { from: 'question', to: 'bench', relation: 'explains' },
    { from: 'code', to: 'bench', relation: 'explains' },
  ],
  checks: [
    // Deciding a pair
    {
      id: 'swap-in-order',
      objectId: 'bench',
      on: ['swap'],
      when: { field: 'outOfOrder', op: 'eq', value: false },
      verdict: 'misconception',
      explain: 'These two were already in order (left ≤ right), so bubble sort keeps them. This swap moved the larger value backwards.',
      respond: {
        say: 'Look at the pair I’ve highlighted: the left value wasn’t bigger, so they were already in order. Bubble sort swaps only when left > right. Swapping here moves the larger value away from the end, and later passes have to undo it. Start over if you’d like a clean trace.',
        calls: [{ name: 'highlight', input: { objectId: 'bench', part: 'last-pair', note: 'left ≤ right: keep' } }],
        once: false,
        topic: 'swap-in-order',
      },
    },
    {
      id: 'keep-out-of-order',
      objectId: 'bench',
      on: ['keep'],
      when: { field: 'outOfOrder', op: 'eq', value: true },
      verdict: 'misconception',
      explain: 'The left value is bigger, so bubble sort swaps them. Keeping them leaves the larger value behind.',
      respond: {
        say: 'In the highlighted pair the left value is bigger, so it has to move right. That is the “bubble”: each swap carries the larger value one step towards the end. Kept here, the largest value can’t reach the end this pass.',
        calls: [{ name: 'highlight', input: { objectId: 'bench', part: 'last-pair', note: 'left > right: swap' } }],
        once: false,
        topic: 'keep-out-of-order',
      },
    },
    {
      id: 'pass-clean',
      objectId: 'bench',
      on: ['swap', 'keep'],
      when: { all: [{ field: 'passEnded', op: 'eq', value: true }, { field: 'passSwaps', op: 'eq', value: 0 }] },
      verdict: 'hint',
      explain: 'A whole pass without a swap: every neighbouring pair is in order, so the algorithm can stop.',
    },
    {
      id: 'pass-ended',
      objectId: 'bench',
      on: ['swap', 'keep'],
      when: { field: 'passEnded', op: 'eq', value: true },
      verdict: 'hint',
      explain: 'Pass done: the largest value left has bubbled to the end (green). The next pass stops one pair earlier.',
    },
    { id: 'decided', objectId: 'bench', on: ['swap', 'keep'], when: { field: 'index', op: 'gte', value: 0 }, verdict: 'hint', explain: '', silent: true },
    // Saying it can stop
    {
      id: 'finish-one-pass',
      objectId: 'bench',
      on: ['finish'],
      when: { all: [{ field: 'sorted', op: 'eq', value: false }, { field: 'passes', op: 'lte', value: 1 }] },
      verdict: 'misconception',
      explain: 'Not sorted yet: one pass only guarantees that the largest value is at the end.',
      respond: {
        say: 'A common trap: one pass doesn’t sort the list. It only guarantees the largest value reaches the end; a small value moves left just one step per pass. Want to watch the whole sort? Accept the suggestion under the bench and I’ll trace it from the start.',
        calls: [{ name: 'demonstrate', input: { objectId: 'bench', actions: trace(values) } }],
        then: onePassNote,
      },
    },
    {
      id: 'finish-unsorted',
      objectId: 'bench',
      on: ['finish'],
      when: { field: 'sorted', op: 'eq', value: false },
      verdict: 'misconception',
      explain: 'Some neighbouring pair is still out of order. Keep passing until a pass makes no swaps.',
      respond: {
        say: 'Not yet: somewhere a left value is still bigger than its right neighbour. Each pass moves it closer, so keep going until a whole pass makes no swaps.',
        once: false,
      },
    },
    {
      id: 'finish-unverified',
      objectId: 'bench',
      on: ['finish'],
      when: { all: [{ field: 'sorted', op: 'eq', value: true }, { field: 'verified', op: 'eq', value: false }] },
      verdict: 'hint',
      explain: 'It is in order, but the algorithm can’t know that yet: its last pass still made a swap.',
      respond: {
        say: 'You’re right that it’s in order, because you can see the whole row at once. The algorithm can’t: it only ever compares one pair. The only way it learns the list is sorted is a pass with no swaps. Run one more pass and watch the swaps column.',
      },
    },
    {
      id: 'finish-done',
      objectId: 'bench',
      on: ['finish'],
      when: { all: [{ field: 'sorted', op: 'eq', value: true }, { field: 'verified', op: 'eq', value: true }] },
      verdict: 'correct',
      explain: 'Sorted, and the last pass made no swaps: that is exactly when the algorithm can stop.',
      completesGoal: true,
      respond: { say: '🎉 Exactly: the last pass made no swaps, so no pair can be out of order. That early exit saved a pass.', calls: counts.calls },
    },
  ],
  intro:
    'Let’s trace it by hand. The five values are bars on the Playground: drag the bigger bar of the highlighted pair past its neighbour to swap them, or slide the arrow on to keep them, and press Done when you think the algorithm can stop.',
  showMe: {
    say: 'Watch my hand: in each pass I compare neighbours left to right and swap when the left one is bigger, so the largest value bubbles to the end. I stop after the first pass with no swaps.',
    calls: [{ name: 'demonstrate', input: { objectId: 'bench', actions: trace(values) } }],
    then: counts,
  },
}
