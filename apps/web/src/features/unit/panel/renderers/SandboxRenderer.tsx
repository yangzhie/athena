import type { PanelContent } from '../types'

type Props = { content: Extract<PanelContent, { kind: 'sandbox' }> }

/** Picks a sandbox component by type. None are built yet. */
export function SandboxRenderer({ content }: Props) {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <p className="text-sm text-muted">No renderer for the “{content.session.type}” sandbox yet.</p>
    </div>
  )
}
