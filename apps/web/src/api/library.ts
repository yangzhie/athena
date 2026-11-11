import type { Material } from '../types'
import { listCourseMaterials } from './materials'

/** Material is always scoped to the open Offering; no Offering means no selection. */
export async function listMaterials(offeringId?: string): Promise<Material[]> {
  if (!offeringId) return []
  return (await listCourseMaterials(offeringId)).map(item => ({
    id: item.id, title: `${item.filename} · v${item.version}`,
    kind: item.kind === 'recording' ? 'recording' : item.filename.endsWith('.pdf') ? 'pdf' : item.filename.endsWith('.pptx') ? 'slides' : 'doc',
    status: item.status === 'queued' ? 'processing' : item.status,
    uploadedAt: new Date(item.created_at * 1000).toISOString(), topicIds: [],
  }))
}
