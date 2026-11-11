import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { listCourseMaterials, publishMaterial, retryMaterial, uploadMaterial, type CourseMaterial } from '../../api/materials'
import { Button, Card } from '../../components/ui'

export default function MaterialManager({ offeringId }: { offeringId: string }) {
  const [items, setItems] = useState<CourseMaterial[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  async function refresh() { setItems(await listCourseMaterials(offeringId)) }
  useEffect(() => {
    let mounted = true
    const load = async () => {
      try { const result = await listCourseMaterials(offeringId); if (mounted) setItems(result) }
      catch (e) { if (mounted) setError(e instanceof Error ? e.message : 'Material unavailable.') }
    }
    void load()
    const timer = setInterval(() => void load(), 4000)
    return () => { mounted = false; clearInterval(timer) }
  }, [offeringId])
  async function action(fn: () => Promise<unknown>) {
    setBusy(true); setError(null)
    try { await fn(); await refresh() }
    catch (e) { setError(e instanceof Error ? e.message : 'Material update failed.') }
    finally { setBusy(false) }
  }
  return <Card title="Course material">
    <p className="mb-4 text-sm text-muted">Upload PDFs, UTF-8 text, DOCX, PPTX or lecture recordings. Processing runs in the worker. Publish ready documents to share them; review proposed lecture clips before learners can watch them.</p>
    <label className="block text-sm font-medium">Upload material
      <input type="file" disabled={busy} accept=".pdf,.txt,.md,.docx,.pptx,.mp4,.mkv,.mov,.webm,.m4a,.mp3,.wav,.flac,.ogg" className="mt-2 block w-full text-sm" onChange={event => {
        const file = event.target.files?.[0]
        if (file) void action(() => uploadMaterial(offeringId, file))
        event.target.value = ''
      }} />
    </label>
    {error && <p role="alert" className="mt-3 text-sm text-bad">{error}</p>}
    <ul className="mt-5 divide-y divide-line">
      {items.map(item => <li key={item.id} className="space-y-2 py-3 text-sm">
        <p className="font-medium">{item.filename} · v{item.version}</p>
        <p className="text-muted">{item.status}{item.published ? ' · Published' : ''}</p>
        {item.error && <p role="alert" className="text-bad">{item.error}</p>}
        {item.status === 'ready' && item.kind === 'document' && !item.published && <Button size="sm" disabled={busy} onClick={() => void action(() => publishMaterial(offeringId, item.id))}>Publish document</Button>}
        {item.status === 'ready' && item.kind === 'recording' && <Link className="text-accent underline" to={`/units/${offeringId}/review`}>Review proposed lecture clips</Link>}
        {item.status === 'failed' && <Button size="sm" disabled={busy} onClick={() => void action(() => retryMaterial(offeringId, item.id))}>Retry processing</Button>}
        <label className="block text-xs text-muted">Replace with a new version
          <input type="file" disabled={busy} onChange={event => {
            const file = event.target.files?.[0]
            if (file) void action(() => uploadMaterial(offeringId, file, item.id))
            event.target.value = ''
          }} />
        </label>
      </li>)}
    </ul>
    {!items.length && <p className="mt-4 text-sm text-muted">No material uploaded yet.</p>}
  </Card>
}
