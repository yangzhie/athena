import { useEffect, useState, type FormEvent } from 'react'
import { addCourseTopic, conceptCatalogue, listCourseTopics, type CourseTopic } from '../../api/progress'
import { Button, Card } from '../../components/ui'

export default function TopicManager({ offeringId }: { offeringId: string }) {
  const [topics, setTopics] = useState<CourseTopic[]>([])
  const [concepts, setConcepts] = useState<{ id: string; name: string }[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    let active = true
    Promise.all([listCourseTopics(offeringId), conceptCatalogue()]).then(([items, catalogue]) => {
      if (active) { setTopics(items); setConcepts(catalogue) }
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : 'Topics unavailable.') })
    return () => { active = false }
  }, [offeringId])
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const input = new FormData(form)
    setBusy(true); setError(null)
    try {
      const topic = await addCourseTopic(offeringId, String(input.get('title')), String(input.get('concept')) || undefined)
      setTopics(items => [...items.filter(item => item.id !== topic.id), topic])
      form.reset()
    } catch (e) { setError(e instanceof Error ? e.message : 'Topic could not be added.') }
    finally { setBusy(false) }
  }
  return <Card title="Course Topics and Concepts">
    <p className="mb-4 text-sm text-muted">Topics guide lecture indexing. Link an unambiguous shared Concept when appropriate; otherwise create an Offering-specific course Concept.</p>
    <form onSubmit={submit} className="space-y-3">
      <label className="block text-sm">Topic title<input name="title" required maxLength={160} className="mt-1 block w-full rounded-lg border border-line bg-surface p-2" /></label>
      <label className="block text-sm">Concept<select name="concept" className="mt-1 block w-full rounded-lg border border-line bg-surface p-2"><option value="">New course Concept</option>{concepts.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <Button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Add Topic'}</Button>
    </form>
    {error && <p role="alert" className="mt-3 text-sm text-bad">{error}</p>}
    <ul className="mt-4 space-y-2 text-sm">{topics.map(item => <li key={item.id}>{item.title} · {concepts.find(c => c.id === item.concept_id)?.name ?? 'Course Concept'}</li>)}</ul>
  </Card>
}
