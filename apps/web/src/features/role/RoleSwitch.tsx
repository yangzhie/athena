import { setRole, useRole, type Role } from '../../app/role'
import { cn } from '../../lib/cn'

const options: { value: Role; label: string }[] = [
  { value: 'student', label: 'Student' },
  { value: 'lecturer', label: 'Lecturer' },
]

/** PoC only: switch between the student and lecturer views. */
export function RoleSwitch() {
  const role = useRole()
  return (
    <div className="border-t border-line pt-3">
      <p className="mb-1.5 px-1 text-xs text-muted">Viewing as (demo)</p>
      <div role="radiogroup" aria-label="View as" className="grid grid-cols-2 gap-1 rounded-lg bg-line/50 p-1">
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={role === o.value}
            onClick={() => setRole(o.value)}
            className={cn(
              'rounded-md px-2 py-1 text-xs font-medium transition-colors',
              role === o.value ? 'bg-surface text-ink shadow-sm' : 'text-muted hover:text-ink',
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}
