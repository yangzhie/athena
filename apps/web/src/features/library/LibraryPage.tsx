import { useLoaderData } from 'react-router'
import { Card } from '../../components/ui'
import { ClipList } from './components/ClipList'
import { MaterialRow } from './components/MaterialRow'
import { UploadDropzone } from './components/UploadDropzone'
import type { libraryLoader } from './loader'

export default function LibraryPage() {
  const { materials, recordings, topicTitles } = useLoaderData<typeof libraryLoader>()

  return (
    <div className="mx-auto max-w-4xl space-y-10">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Library</h1>
        <p className="mt-1 text-muted">
          Your own materials. Athena uses them as the source for explanations and questions, and cites them.
        </p>
      </header>

      <UploadDropzone />

      <section>
        <h2 className="mb-3 text-lg font-semibold">Materials</h2>
        {materials.length === 0 ? (
          <p className="text-muted">Nothing uploaded yet.</p>
        ) : (
          <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
            {materials.map((m) => (
              <MaterialRow key={m.id} material={m} topicTitles={topicTitles} />
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Lecture clips</h2>
        {recordings.length === 0 ? (
          <p className="text-muted">Upload a lecture recording and Athena will split it into clips by topic.</p>
        ) : (
          <div className="space-y-4">
            {recordings.map((r) => (
              <Card key={r.id} title={r.title}>
                <ClipList clips={r.clips} topicTitles={topicTitles} />
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
