import { useEffect, useState } from 'react'
import { listCourseMaterials, listSourcePassages, sourceFileUrl, type CourseMaterial } from '../../../api/materials'
import { Button, Card } from '../../../components/ui'
import { openInPanel } from '../panel/panelStore'
import { useOffering } from '../useOffering'

export default function LibraryView() {
  const offering = useOffering()
  const [items, setItems] = useState<CourseMaterial[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let mounted = true
    listCourseMaterials(offering.id).then(result => { if (mounted) setItems(result) }).catch(e => {
      if (mounted) setError(e instanceof Error ? e.message : 'Material library unavailable.')
    })
    return () => { mounted = false }
  }, [offering.id])
  async function open(item: CourseMaterial) {
    try {
      const [passage] = await listSourcePassages(offering.id, item.id)
      if (!passage) throw new Error('No readable passage is available for this source.')
      openInPanel(offering.id, { kind: 'source', source: { kind: 'document', sourceId: item.id,
        passageId: passage.id, title: `${item.filename} · v${item.version}`, quote: passage.text,
        page: passage.page ?? undefined, section: passage.section ?? undefined } })
    } catch (e) { setError(e instanceof Error ? e.message : 'Source unavailable.') }
  }
  const documents = items?.filter(item => item.kind === 'document' && item.status === 'ready')
  return <section className="mx-auto w-full max-w-3xl space-y-5 pb-10">
    <h1 className="text-2xl font-semibold">Material library</h1>
    <p className="text-sm text-muted">{offering.unit.code} · Published course documents. Approved recordings are in Lecture clips.</p>
    {error && <p role="alert" className="text-sm text-bad">{error}</p>}
    {!items && !error && <p>Loading material…</p>}
    {documents?.map(item => <Card key={item.id} title={`${item.filename} · v${item.version}`}>
      <Button size="sm" onClick={() => void open(item)}>Read source</Button>
      <a className="ml-4 text-sm text-accent underline" href={sourceFileUrl(offering.id, item.id)}>Download</a>
    </Card>)}
    {documents?.length === 0 && <p className="text-muted">No published documents are available yet.</p>}
  </section>
}
