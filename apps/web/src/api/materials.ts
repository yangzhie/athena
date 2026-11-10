import { call } from './client'

export interface CourseMaterial {
  id: string
  source_id: string
  version: number
  offering_id: string
  filename: string
  kind: 'document' | 'recording'
  size: number
  created_at: number
  status: 'queued' | 'processing' | 'ready' | 'failed'
  published: boolean
  error: string | null
}
const base = (offering: string) => `/units/${encodeURIComponent(offering)}/materials`
export const listCourseMaterials = (offering: string): Promise<CourseMaterial[]> => call(base(offering))
export const uploadMaterial = (offering: string, file: File, replace?: string): Promise<CourseMaterial> =>
  call(`${base(offering)}?filename=${encodeURIComponent(file.name)}${replace ? `&replace=${encodeURIComponent(replace)}` : ''}`, { method: 'POST', body: file })
export const publishMaterial = (offering: string, id: string): Promise<CourseMaterial> => call(`${base(offering)}/${id}/publish`, { method: 'POST' })
export const retryMaterial = (offering: string, id: string): Promise<CourseMaterial> => call(`${base(offering)}/${id}/retry`, { method: 'POST' })

export interface SourcePassage { id: string; page: number | null; section: string | null; text: string; filename: string; version: number }
export const getSourcePassage = (offering: string, source: string, passage: string): Promise<SourcePassage> =>
  call(`${base(offering)}/${encodeURIComponent(source)}/passages/${encodeURIComponent(passage)}`)
export const listSourcePassages = (offering: string, source: string): Promise<Omit<SourcePassage, 'filename' | 'version'>[]> =>
  call(`${base(offering)}/${encodeURIComponent(source)}/passages`)
export const sourceFileUrl = (offering: string, source: string) => `/api${base(offering)}/${encodeURIComponent(source)}/file`
