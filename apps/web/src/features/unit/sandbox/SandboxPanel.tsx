import { Badge } from '../../../components/ui'
import type { SandboxSession } from '../../../types'

/**
 * Right-hand panel where the tutor's interactive sandboxes open
 * (Python runner, subnet visualiser, molecule viewer...).
 * Empty placeholder for now; `session` will come from the tutor's propose_sandbox tool.
 */
export function SandboxPanel({ session = null }: { session?: SandboxSession | null }) {
  return (
    <section aria-labelledby="sandbox-title" className="flex h-full flex-col rounded-2xl border border-line bg-surface">
      <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
        <h2 id="sandbox-title" className="font-semibold">
          {session?.title ?? 'Sandbox'}
        </h2>
        <Badge>{session ? session.type : 'empty'}</Badge>
      </header>

      <div className="flex flex-1 items-center justify-center p-6">
        {session ? (
          // Sandbox renderers plug in here, chosen by session.type.
          <p className="text-sm text-muted">No renderer for “{session.type}” yet.</p>
        ) : (
          <div className="max-w-xs text-center">
            <div
              className="mx-auto mb-4 grid size-12 place-items-center rounded-xl bg-accent-soft text-accent"
              aria-hidden
            >
              <svg viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth={1.75}>
                <path d="M8 9l-3 3 3 3M16 9l3 3-3 3M13.5 6l-3 12" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <p className="font-medium">Nothing open yet</p>
            <p className="mt-1 text-sm text-muted">
              When the tutor suggests something hands-on, like running Python or visualising a data structure, it opens
              here next to the chat.
            </p>
          </div>
        )}
      </div>
    </section>
  )
}
