import { useRef, useState, type FormEvent } from 'react'
import { Button } from '../../components/ui'

const SEMESTERS = ['Semester 1', 'Semester 2', 'Summer'] as const

const field =
  'h-10 w-full rounded-lg border border-line bg-surface px-3 text-sm outline-none focus:border-accent'

/**
 * Lecturer action: create a study space for a unit offering (e.g. CSE5DMI, Sem 2 2026).
 * Dummy for now. Nothing is saved, and there are no roles yet, so everyone sees it.
 */
export function CreateSpaceButton() {
  const dialog = useRef<HTMLDialogElement>(null)
  const [submitted, setSubmitted] = useState<string | null>(null)

  function open() {
    setSubmitted(null)
    dialog.current?.showModal()
  }

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const data = new FormData(e.currentTarget)
    setSubmitted(`${String(data.get('code')).toUpperCase()} · ${data.get('semester')} ${data.get('year')}`)
    e.currentTarget.reset()
  }

  return (
    <>
      <Button variant="secondary" size="sm" onClick={open} className="w-full">
        + New study space
      </Button>

      <dialog
        ref={dialog}
        aria-labelledby="create-space-title"
        className="m-auto w-[calc(100%-2rem)] max-w-md rounded-xl border border-line bg-surface p-0 text-ink backdrop:bg-black/40"
      >
        <div className="p-6">
          <h2 id="create-space-title" className="text-lg font-semibold">
            New study space
          </h2>
          <p className="mt-1 text-sm text-muted">
            For lecturers. Create a space for one offering of a unit, then upload its material and enrol students.
          </p>

          {submitted ? (
            <div className="mt-5 space-y-4">
              <p className="rounded-lg bg-warn/15 px-3 py-2 text-sm">
                <span className="font-medium">{submitted}</span> was not created. The backend isn't connected yet.
              </p>
              <div className="flex justify-end">
                <Button variant="secondary" onClick={() => dialog.current?.close()}>
                  Close
                </Button>
              </div>
            </div>
          ) : (
            <form onSubmit={submit} className="mt-5 space-y-4">
              <div className="grid gap-4 sm:grid-cols-[8rem_1fr]">
                <label className="block text-sm">
                  <span className="mb-1 block font-medium">Unit code</span>
                  <input
                    name="code"
                    required
                    placeholder="CSE5DMI"
                    autoComplete="off"
                    className={`${field} uppercase placeholder:normal-case`}
                  />
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block font-medium">Unit title</span>
                  <input name="title" required placeholder="Data Mining" className={field} />
                </label>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <label className="block text-sm">
                  <span className="mb-1 block font-medium">Year</span>
                  <input
                    name="year"
                    type="number"
                    required
                    min={2000}
                    max={2100}
                    defaultValue={new Date().getFullYear()}
                    className={field}
                  />
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block font-medium">Semester</span>
                  <select name="semester" defaultValue="Semester 2" className={field}>
                    {SEMESTERS.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="ghost" onClick={() => dialog.current?.close()}>
                  Cancel
                </Button>
                <Button type="submit">Create study space</Button>
              </div>
            </form>
          )}
        </div>
      </dialog>
    </>
  )
}
