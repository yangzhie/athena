import type { Material } from '../types'
import { materials } from '../mocks/data'

export async function listMaterials(): Promise<Material[]> {
  return materials
}
