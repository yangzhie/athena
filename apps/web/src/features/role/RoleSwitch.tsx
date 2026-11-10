import { useState, type FormEvent } from 'react'
import { useRevalidator } from 'react-router'
import { enableLecturerAccess } from '../../api/spaces'
import { useServerIdentity } from '../../app/identity'
import { setRole, useRole, type Role } from '../../app/role'
import { cn } from '../../lib/cn'

const options: { value: Role; label: string }[] = [
  { value: 'student', label: 'Student' },
  { value: 'lecturer', label: 'Lecturer' },
]

/** Lecturer authority is issued by the server; this switch only chooses a view. */
export function RoleSwitch() {
  const role = useRole()
  const identity = useServerIdentity()
  const revalidator = useRevalidator()
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function activate(event: FormEvent) {
    event.preventDefault()
    setBusy(true); setError(null)
    try {
      await enableLecturerAccess(code.trim())
      setCode(''); setRole('lecturer')
      await revalidator.revalidate()
    } catch (error) { setError(error instanceof Error ? error.message : 'Lecturer access unavailable.') }
    finally { setBusy(false) }
  }
  if (identity.role !== 'lecturer') return <div className="border-t border-line pt-3 text-xs text-muted">
    <p>Student</p>
    <details className="mt-2"><summary className="cursor-pointer">Lecturer access</summary>
      <p className="my-2">Use a one-time invite from the Athena administrator.</p>
      <form onSubmit={activate} className="space-y-2">
        <input aria-label="Lecturer invite code" type="password" autoComplete="off" value={code} onChange={(event) => setCode(event.target.value)} className="w-full rounded border border-line bg-surface p-2 text-ink" />
        <button disabled={busy || !code.trim()} className="text-accent" type="submit">Enable lecturer access</button>
        {error && <p role="alert" className="text-bad">{error}</p>}
      </form>
    </details>
  </div>
  return <div className="border-t border-line pt-3">
    <p className="mb-1.5 px-1 text-xs text-muted">Viewing as</p>
    <div role="radiogroup" aria-label="View as" className="grid grid-cols-2 gap-1 rounded-lg bg-line/50 p-1">
      {options.map((option) => <button key={option.value} type="button" role="radio" aria-checked={role === option.value} onClick={() => setRole(option.value)} className={cn('rounded-md px-2 py-1 text-xs font-medium transition-colors', role === option.value ? 'bg-surface text-ink shadow-sm' : 'text-muted hover:text-ink')}>{option.label}</button>)}
    </div>
  </div>
}
