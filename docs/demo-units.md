# Demo units

Three units for demonstrating Athena end to end: uploaded lecture notes, lecture
indexing (transcription and topic clips), grounded tutor sessions with citations,
Practice and the Playground.

| Unit | Lecture PDF | Lecture recording | Fits Playground objects |
| --- | --- | --- | --- |
| CHEM1001 Principles of Chemical Science | Lecture 25 notes: Oxidation-Reduction and Electrochemical Cells | Lecture 25 (53 min) | half-cell, salt bridge, voltmeter |
| PHYS1001 Classical Mechanics | Chapter 7: Newton's Laws of Motion | Lecture 6: Newton's Laws (49 min) | force lab |
| COMP1001 Introduction to Programming in Python | Lecture 1 slides: What is computation | Lecture 1 (43 min) | code graph |

The units and files are defined in [`scripts/demo-units.json`](../scripts/demo-units.json).

## Seed them

With the stack running (`npm run dev:all`), from the repository root:

```sh
apps/api/.venv/bin/python scripts/seed-demo.py
```

The script downloads about 340 MB into `data/demo/downloads/` (gitignored). It then
acts as a demo lecturer through the normal API: creates each Offering, adds topics,
uploads the files, waits for processing, publishes the materials, approves the
proposed clips and publishes the Offering.

- **Time:** about 5 minutes of local Whisper transcription per recording on a laptop
  CPU, plus a few model calls each for topic segmentation (`OPENAI_API_KEY` and
  `OPENAI_MODEL` must be set).
- **Re-runs** are safe: finished steps are skipped (`data/demo/seed-state.json`).
- `--only CHEM1001` seeds one unit. `--keep-pending` leaves clips unapproved so a
  lecturer can review them live.

## Start the demo sessions in your browser

Each unit has two `session_goals` in the manifest: "What is electrochemistry?" and
"What is a redox reaction?" (CHEM1001), "Centrifugal force" and "Potential energy vs
kinetic energy" (PHYS1001), and "Testing bubble sort" and "Linked lists" (COMP1001).
Sessions are private to a browser identity, so they're started for the browser you'll
demo with. A different browser, profile or private window is a different identity
and won't show them.

1. Open http://127.0.0.1:5173 in that browser once.
2. In developer tools, open Application, then Cookies, then `http://127.0.0.1:5173`,
   and copy the value of `athena_session`.
3. Run:

   ```sh
   apps/api/.venv/bin/python scripts/seed-demo.py --sessions-only --sessions-for-cookie '<value>'
   ```

Each unit then shows its session, opened by the tutor with a first question. This
makes a few model calls per session. The cookie is used for these requests only and
isn't saved. Re-running never creates duplicates.

## Sample Progress and Insights

Progress (student) and Insights (lecturer) need assessment history, so the demo can add
invented sample data from each unit's `sample_data` in the manifest:

```sh
apps/api/.venv/bin/python scripts/seed-demo.py --sample-data --sessions-for-cookie '<value>'
```

- **Insights:** a fake cohort of 22–31 anonymous Environments per unit, with each topic's
  share of assessments needing more work and its 95% confidence interval.
- **Progress:** your browser's answers per topic, with the share answered correctly and
  its 95% interval (Wilson score). Without the cookie, only the cohort is added.

Both views show a "Sample data" label while any of it is present. All rows have ids
starting with `sample:`. Remove them with `--remove-sample-data`. Cohort rows also
expire with the 30-day retention sweep.

## Show the lecturer side

The demo Offerings belong to the seed script's lecturer identity, because only an
Offering's creator can manage it. To act as that lecturer in the browser, copy
`lecturer_cookie` from `data/demo/seed-state.json`, then in the browser's developer
tools set a cookie named `athena_session` with that value for `127.0.0.1`
(Application, then Cookies), and reload. Use a private window to keep your own
identity separate.

## Licences and attribution

All materials are from MIT OpenCourseWare, used under Creative Commons
Attribution-NonCommercial-ShareAlike licences. They're for non-commercial
demonstration only, are downloaded at seed time and are never committed.
Some OCW files contain third-party images excluded from the Creative Commons
licence; see each source page.

- **Chemistry.** Catherine Drennan and Elizabeth Vogel Taylor. *5.111SC Principles
  of Chemical Science*, Fall 2014. MIT OpenCourseWare,
  [course page](https://ocw.mit.edu/courses/5-111sc-principles-of-chemical-science-fall-2014/).
  Notes: CC BY-NC-SA 4.0. Video: [Internet Archive](https://archive.org/details/MIT5.111F14), CC BY-NC-SA 3.0.
- **Physics.** Textbook: Deepto Chakrabarty, Peter Dourmashkin, Michelle Tomasik,
  Anna Frebel and Vladan Vuletic. *8.01SC Classical Mechanics*, Fall 2016. MIT
  OpenCourseWare, [course page](https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/),
  CC BY-NC-SA 4.0. Lecture: Walter Lewin. *8.01 Physics I: Classical Mechanics*,
  Fall 1999. MIT OpenCourseWare, [Internet Archive](https://archive.org/details/MIT8.01F99),
  CC BY-NC-SA 3.0 US.
- **Coding.** Ana Bell, Eric Grimson and John Guttag. *6.0001 Introduction to
  Computer Science and Programming in Python*, Fall 2016. MIT OpenCourseWare,
  [course page](https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/).
  Slides: CC BY-NC-SA 4.0. Video: [Internet Archive](https://archive.org/details/MIT6.0001F16), CC BY-NC-SA 3.0.

Licences: [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/),
[CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/).
