import { useRef, useState, type FormEvent } from 'react'
import { useNavigate, useRevalidator } from 'react-router'
import { useRole } from '../../app/role'
import { createStudySpace } from '../../api/spaces'
import { Button } from '../../components/ui'

const SEMESTERS = ['Semester 1', 'Semester 2', 'Summer'] as const

const field =
  'h-10 w-full rounded-lg border border-line bg-surface px-3 text-sm outline-none focus:border-accent'

/**
 * Lecturer action: create a study space for a unit offering (e.g. CSE5DMI, Sem 2 2026).
 * The server grants management to this browser identity when it creates the draft.
 */
export function CreateSpaceButton() {
  const role = useRole()
  const dialog = useRef<HTMLDialogElement>(null)
  const [submitted, setSubmitted] = useState<string | null>(null)
  const navigate = useNavigate()
  const revalidator = useRevalidator()
  const [busy, setBusy] = useState(false)

  function open() {
    setSubmitted(null)
    dialog.current?.showModal()
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const data = new FormData(e.currentTarget)
    setBusy(true)
    try {
      const offering = await createStudySpace({ code: String(data.get('code')).toUpperCase(), title: String(data.get('title')), year: Number(data.get('year')), semester: String(data.get('semester')) })
      dialog.current?.close()
      void revalidator.revalidate()
      navigate(`/units/${offering.id}/manage`)
    } catch (error) { setSubmitted(error instanceof Error ? error.message : 'Study space could not be created.') }
    finally { setBusy(false) }
  }


  if (role !== 'lecturer') return null

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
            Create a study space for one Offering. It starts as a private draft. You can upload material and choose when to publish it.
          </p>

          {submitted ? (
            <div className="mt-5 space-y-4">
              <p className="rounded-lg bg-warn/15 px-3 py-2 text-sm">
                <span role="alert">{submitted}</span>
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
                <Button type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create study space'}</Button>
              </div>
            </form>
          )}
        </div>
      </dialog>
    </>
  )
}
