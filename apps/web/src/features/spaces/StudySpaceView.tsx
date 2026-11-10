import TopicManager from './TopicManager'
import MaterialManager from './MaterialManager'
import { useState } from 'react'
import { useRevalidator } from 'react-router'
import { publishStudySpace } from '../../api/spaces'
import { Button, Card } from '../../components/ui'
import { useOffering } from '../unit/useOffering'

export default function StudySpaceView() {
  const offering = useOffering()
  const revalidator = useRevalidator()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  async function publish() {
    setBusy(true)
    setError(null)
    try { await publishStudySpace(offering.id); void revalidator.revalidate() }
    catch (e) { setError(e instanceof Error ? e.message : 'Publication failed.') }
    finally { setBusy(false) }
  }
  if (!offering.can_manage) return <p role="alert">Only the creator of this study space can manage it.</p>
  return <section className="mx-auto w-full max-w-3xl space-y-6 pb-10">
    <h1 className="text-2xl font-semibold">{offering.unit.code} · Study space</h1>
    <p className="text-muted">{offering.unit.title} · {offering.semester} {offering.year}</p>
    <Card title={offering.status === 'draft' ? 'Private draft' : 'Published Offering'}>
      <p className="text-sm text-muted">Publishing makes this Offering and its published material available to everyone using this Athena instance. Each learner’s conversations, answers and notes stay in their private Environment.</p>
      <p className="mt-3 text-sm text-muted">Management belongs to this browser. Keep its cookies to retain access; there is no account recovery in this version.</p>
      {offering.status === 'draft' && <Button className="mt-4" disabled={busy} onClick={publish}>{busy ? 'Publishing…' : 'Publish study space'}</Button>}
      {error && <p role="alert" className="mt-3 text-sm text-bad">{error}</p>}
    </Card>
    <TopicManager key={`topics-${offering.id}`} offeringId={offering.id} />
    <MaterialManager key={offering.id} offeringId={offering.id} />
  </section>
}
