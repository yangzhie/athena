import type { Feedback, Proposal, Provenance } from '../contracts'
import { cn } from './cn'
import type { Playground } from './store'

const PROVENANCE: Record<Provenance, { label: string; className: string }> = {
  'real-run': { label: 'Real run', className: 'bg-good/15 text-good' },
  simulated: { label: 'Simulated', className: 'bg-warn/15 text-warn' },
  'ai-estimate': { label: 'AI estimate', className: 'bg-warn/15 text-warn' },
  concept: { label: 'Concept sketch', className: 'bg-line text-muted' },
  material: { label: 'Unit material', className: 'bg-accent-soft text-accent' },
}

const VERDICT = {
  correct: { icon: '✓', label: 'Correct', className: 'border-good/40 bg-good/10 text-good' },
  hint: { icon: '💡', label: 'Hint', className: 'border-warn/40 bg-warn/10 text-warn' },
  misconception: { icon: '⚠', label: 'Common misconception', className: 'border-bad/40 bg-bad/10 text-bad' },
  unmatched: { icon: '…', label: 'Over to the tutor', className: 'border-line bg-bg text-muted' },
}

export function ProvenanceTag({ provenance }: { provenance: Provenance }) {
  const p = PROVENANCE[provenance]
  return <span className={cn('shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium', p.className)}>{p.label}</span>
}

/** Instant feedback from a matched check (or the hand-off when nothing matched). */
export function FeedbackBar({ feedback, className }: { feedback: Feedback; className?: string }) {
  const v = VERDICT[feedback.verdict]
  return (
    <div key={feedback.at} className={cn('animate-[pg-pop_.25s_ease-out] px-3 py-2 text-xs', v.className, className)}>
      <span className="mr-1 font-semibold">
        {v.icon} {v.label}
      </span>
      {feedback.text}
    </div>
  )
}

/** A change the agent proposes; nothing changes until the student accepts. */
export function ProposalBar({ proposal, playground }: { proposal: Proposal; playground: Playground }) {
  return (
    <div className="border-b border-accent/30 bg-accent-soft px-3 py-2 text-xs" onPointerDown={(e) => e.stopPropagation()}>
      <p className="font-medium text-accent">Tutor suggests: {proposal.summary}</p>
      {proposal.diff && (
        <pre className="mt-1.5 overflow-x-auto rounded border border-line bg-surface font-mono text-[11px] leading-5">
          {proposal.diff.before.split('\n').map((l, i) => (
            <div key={`b${i}`} className="bg-bad/10 px-2 text-bad">
              − {l}
            </div>
          ))}
          {proposal.diff.after.split('\n').map((l, i) => (
            <div key={`a${i}`} className="bg-good/10 px-2 text-good">
              + {l}
            </div>
          ))}
        </pre>
      )}
      {proposal.config && !proposal.diff && <p className="mt-1 text-muted">This replaces your changes to this object.</p>}
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={() => playground.acceptProposal(proposal.id)}
          className="rounded-md bg-accent px-2.5 py-1 font-medium text-white hover:opacity-90"
        >
          {proposal.thenDemonstrate ? 'Apply and show me' : 'Apply'}
        </button>
        <button
          type="button"
          onClick={() => playground.rejectProposal(proposal.id)}
          className="rounded-md border border-line bg-surface px-2.5 py-1 hover:bg-bg"
        >
          No thanks
        </button>
      </div>
    </div>
  )
}
