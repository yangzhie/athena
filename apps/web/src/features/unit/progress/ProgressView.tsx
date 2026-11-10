import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { getLearnerProfile, getProgress, type ConceptProgress } from '../../../api/progress'
import { Card } from '../../../components/ui'
import { useOffering } from '../useOffering'

export default function ProgressView() {
  const offering = useOffering()
  const [progress, setProgress] = useState<ConceptProgress[] | null>(null)
  const [profile, setProfile] = useState<ConceptProgress[]>([])
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let active = true
    Promise.all([getProgress(offering.id), getLearnerProfile()]).then(([items, all]) => {
      if (active) { setProgress(items); setProfile(all) }
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : 'Progress unavailable.') })
    return () => { active = false }
  }, [offering.id])
  return <section className="mx-auto w-full max-w-3xl space-y-5 pb-10">
    <h1 className="text-2xl font-semibold">Your learning progress</h1>
    <p className="text-sm text-muted">Private to this browser identity. Your learner profile can help across Units; every learning session starts a fresh conversation.</p>
    {error && <p role="alert" className="text-bad">{error}</p>}
    {!progress && !error && <p>Loading progress…</p>}
    {progress?.map(concept => <Card key={concept.id} title={concept.name}>
      <p className="text-sm font-medium capitalize">{concept.status}</p>
      <p className="mt-2 text-sm text-muted">{concept.note} · {concept.evidence_count} assessment records</p>
      <p className="mt-2 text-sm">{concept.next_action}</p>
    </Card>)}
    {progress?.length === 0 && <p className="text-muted">No assessed Concepts in this Offering yet. Start a learning session to diagnose your understanding.</p>}
    <Link className="inline-block text-sm text-accent underline" to={`/units/${offering.id}/practice`}>Open Practice</Link>
    <details className="text-sm"><summary className="cursor-pointer font-medium">Your cross-unit learner profile</summary>
      <ul className="mt-3 space-y-2">{profile.map(item => <li key={item.id}>{item.name} · {item.status}</li>)}</ul>
      <p className="mt-3 text-muted">Only explicitly shared canonical Concepts transfer across Units. Ambiguous Concepts stay scoped to their Offering. Practice scheduling alone does not establish mastery.</p>
    </details>
  </section>
}
