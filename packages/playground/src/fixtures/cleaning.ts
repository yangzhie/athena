import type { Scene } from '../contracts'

/**
 * TEST FIXTURE. A hand-written scene standing in for what the agent would
 * generate from the unit's material and the student's question.
 */
export const cleaningScene: Scene = {
  id: 'cleaning-average',
  title: 'Programming · Data cleaning',
  goal: 'Make the average leave out only missing values: it should be 10.0, not 15.0',
  objects: [
    {
      id: 'question',
      type: 'note',
      title: 'The question',
      provenance: 'material',
      sources: [{ label: 'Sample material: cleaning.py' }],
      config: {
        markdown:
          'In the sensor readings `[0, 10, None, 20]`, **0 is a real measurement** and **None means missing**.\n\nThe average should leave out only the missing value, but the program prints 15.0. What is going wrong?\n\nTry dragging test values onto the filter node to see which ones it keeps.',
      },
    },
    {
      id: 'cleaning',
      type: 'code-graph',
      title: 'cleaning.py',
      provenance: 'material',
      experimentId: 'cleaning',
      near: 'question',
      sources: [{ label: 'Sample material: cleaning.py' }],
      config: {
        language: 'python',
        probeValues: ['0', 'None', '10', '-5'],
        source: [
          '# 0 is a real measurement; None means missing',
          'values = [0, 10, None, 20]',
          '',
          'def clean(values):',
          '    return [x for x in values if x]',
          '',
          'cleaned = clean(values)',
          'total = sum(cleaned)',
          'count = len(cleaned)',
          'average = total / count if count else None',
          '',
          'print("Kept:", cleaned)',
          'print("Average:", average)',
        ].join('\n'),
      },
    },
  ],
  links: [{ from: 'question', to: 'cleaning', relation: 'explains' }],
  checks: [
    // Probing the filter
    {
      id: 'probe-zero-dropped',
      objectId: 'cleaning',
      on: ['probe'],
      when: { all: [{ field: 'value', op: 'eq', value: '0' }, { field: 'kept', op: 'eq', value: false }] },
      verdict: 'misconception',
      explain: '0 was dropped: `if x` treats 0 as false, so a real measurement is handled as if it were missing.',
      respond: {
        say: "You found it. `if x` tests whether x is truthy, and 0 is falsy in Python, so the real reading 0 is thrown away along with the missing None. We only want to drop None. I suggest changing the condition to `x is not None`; accept it and I'll run it for you.",
        calls: [
          { name: 'highlight', input: { objectId: 'cleaning', part: 'cleaned', note: 'if x drops both 0 and None' } },
          {
            name: 'edit_node',
            input: {
              objectId: 'cleaning',
              nodeId: 'cleaned',
              condition: 'x is not None',
              reason: 'drop only the missing value None and keep the real reading 0',
              demonstrateAfter: true,
            },
          },
        ],
        then: {
          say: "I've pinned both runs next to the code: 0 now counts (three numbers), and None is still left out.",
          calls: [
            {
              name: 'add_object',
              input: {
                object: {
                  id: 'before-after',
                  type: 'result',
                  title: 'Two runs compared',
                  provenance: 'simulated',
                  experimentId: 'cleaning',
                  near: 'cleaning',
                  config: {
                    compareRuns: { value: 'average', also: 'cleaned' },
                    caption: 'Both runs come from the code graph next to it.',
                  },
                },
              },
            },
            { name: 'link', input: { from: 'cleaning', to: 'before-after', relation: 'from' } },
          ],
        },
      },
    },
    {
      id: 'probe-error',
      objectId: 'cleaning',
      on: ['probe'],
      when: { field: 'kept', op: 'eq', value: 'error' },
      verdict: 'misconception',
      explain: 'The condition fails on this value: None can’t be compared with a number (TypeError).',
      respond: {
        say: 'In Python 3, a comparison like `None > 0` raises a TypeError: None has no size. Check for None on its own first, for example `x is not None`.',
        calls: [{ name: 'highlight', input: { objectId: 'cleaning', part: 'cleaned' } }],
        once: false,
        topic: 'type-error',
      },
    },
    {
      id: 'probe-none-dropped',
      objectId: 'cleaning',
      on: ['probe'],
      when: { all: [{ field: 'value', op: 'eq', value: 'None' }, { field: 'kept', op: 'eq', value: false }] },
      verdict: 'hint',
      explain: 'None is filtered out, which is what we want. What about 0?',
    },
    {
      id: 'probe-kept',
      objectId: 'cleaning',
      on: ['probe'],
      when: { field: 'kept', op: 'eq', value: true },
      verdict: 'hint',
      explain: 'This value is kept. Now try 0 and None.',
    },
    // Editing the condition
    {
      id: 'edit-none-compare',
      objectId: 'cleaning',
      on: ['editCondition'],
      when: { field: 'keeps.None', op: 'eq', value: 'error' },
      verdict: 'misconception',
      explain: 'This condition compares None with a number, which raises a TypeError. Check for None first.',
      respond: {
        say: 'In Python 3, a comparison like `None > 0` raises a TypeError: None has no size. Check for None on its own first, for example `x is not None`.',
        calls: [{ name: 'highlight', input: { objectId: 'cleaning', part: 'cleaned' } }],
        once: false,
        topic: 'type-error',
      },
    },
    {
      id: 'edit-still-drops-zero',
      objectId: 'cleaning',
      on: ['editCondition'],
      when: { field: 'keeps.0', op: 'eq', value: false },
      verdict: 'misconception',
      explain: '0 is still dropped: this still treats “zero” as “missing”.',
      respond: {
        say: 'Careful: this condition still drops 0. A 0 is a real measurement (say, exactly 0 degrees); it is just small. Only None means missing. Which condition drops None and nothing else?',
        calls: [{ name: 'highlight', input: { objectId: 'cleaning', part: 'cleaned' } }],
        once: false,
      },
    },
    {
      id: 'edit-keeps-none',
      objectId: 'cleaning',
      on: ['editCondition'],
      when: { field: 'keeps.None', op: 'eq', value: true },
      verdict: 'misconception',
      explain: 'None would be kept, and sum() fails when it meets None.',
      respond: { say: 'Now None reaches sum(), and adding None to a number fails. The condition needs to drop None.', once: false },
    },
    {
      id: 'edit-looks-right',
      objectId: 'cleaning',
      on: ['editCondition'],
      when: { all: [{ field: 'keeps.0', op: 'eq', value: true }, { field: 'keeps.None', op: 'eq', value: false }] },
      verdict: 'hint',
      explain: '0 is kept and None is dropped. Looks right: press Run to check.',
    },
    // Running
    {
      id: 'run-correct',
      objectId: 'cleaning',
      on: ['runCompleted'],
      when: { field: 'value.average', op: 'eq', value: '10.0' },
      verdict: 'correct',
      explain: 'The average is 10.0: 0 counts, and only None is left out.',
      completesGoal: true,
    },
    {
      id: 'run-still-15',
      objectId: 'cleaning',
      on: ['runCompleted'],
      when: { field: 'value.average', op: 'eq', value: '15.0' },
      verdict: 'hint',
      explain: '15.0 = (10 + 20) / 2: only two numbers were averaged. Which one went missing?',
    },
    {
      id: 'run-error',
      objectId: 'cleaning',
      on: ['runCompleted'],
      when: { field: 'ok', op: 'eq', value: false },
      verdict: 'misconception',
      explain: 'The run failed. Look at which node and which value caused the error.',
      respond: {
        say: 'In Python 3, a comparison like `None > 0` raises a TypeError: None has no size. Check for None on its own first, for example `x is not None`.',
        calls: [{ name: 'highlight', input: { objectId: 'cleaning', part: 'cleaned' } }],
        once: false,
        topic: 'type-error',
      },
    },
  ],
  intro:
    'This is easier to see by trying it. I’ve split the code into a data-flow graph on the Playground. Drag the test values onto the filter node and see which ones survive.',
  showMe: {
    say: "I'll change the filter condition first (it only applies once you accept), then run it so you can watch the data flow through the nodes.",
    calls: [
      {
        name: 'edit_node',
        input: {
          objectId: 'cleaning',
          nodeId: 'cleaned',
          condition: 'x is not None',
          reason: 'drop only the missing value None and keep the real reading 0',
          demonstrateAfter: true,
        },
      },
    ],
    then: {
      say: "I've pinned both runs next to the code: 0 now counts (three numbers), and None is still left out.",
      calls: [
        {
          name: 'add_object',
          input: {
            object: {
              id: 'before-after',
              type: 'result',
              title: 'Two runs compared',
              provenance: 'simulated',
              experimentId: 'cleaning',
              near: 'cleaning',
              config: {
                compareRuns: { value: 'average', also: 'cleaned' },
                caption: 'Both runs come from the code graph next to it.',
              },
            },
          },
        },
        { name: 'link', input: { from: 'cleaning', to: 'before-after', relation: 'from' } },
      ],
    },
  },
}
