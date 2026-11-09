import type { LectureClip, Material } from '../types'
import { lectureClips, materials } from '../mocks/data'

export async function listMaterials(): Promise<Material[]> {
  return materials
}

export async function listClips(topicId?: string): Promise<LectureClip[]> {
  return topicId ? lectureClips.filter((c) => c.topicId === topicId) : lectureClips
}
