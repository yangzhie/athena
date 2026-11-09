import { listTopics } from '../../api/learning'
import { listClips, listMaterials } from '../../api/library'

export async function libraryLoader() {
  const [materials, clips, topics] = await Promise.all([listMaterials(), listClips(), listTopics()])
  return {
    materials,
    // Clips grouped under the recording they come from.
    recordings: materials
      .filter((m) => m.kind === 'recording')
      .map((m) => ({ ...m, clips: clips.filter((c) => c.materialId === m.id).sort((a, b) => a.startS - b.startS) }))
      .filter((r) => r.clips.length > 0),
    topicTitles: Object.fromEntries(topics.map((t) => [t.id, t.title])),
  }
}
