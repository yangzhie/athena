/** Lecturer-only: a unit's SRS question bank, with answers. See apps/api README. */
import { call } from './client'

export type VariantStatus = 'approved' | 'pending' | 'rejected'
export type VariantOrigin = 'bank' | 'generated' | 'live'

interface VariantBase {
  id: string
  stem: string
  explanation: string
  origin: VariantOrigin
  status: VariantStatus
}

export type BankVariant =
  | (VariantBase & { kind: 'mcq'; options: string[]; answer_index: number })
  | (VariantBase & { kind: 'numeric'; answer: number; tolerance: number })
  | (VariantBase & { kind: 'short'; model_answer: string; rubric: string[] })

export interface BankItem {
  id: string
  offering_id: string
  topic_id: string
  concept: string
  difficulty: number
  bloom: 'recall' | 'apply' | 'analyse'
  variants: BankVariant[]
  clip_ids: string[]
}

export interface Bank {
  offering_id: string
  items: BankItem[]
}

const base = (offeringId: string) => `/units/${encodeURIComponent(offeringId)}/srs/bank`
const variantPath = (o: string, item: string, variant: string) =>
  `${base(o)}/items/${encodeURIComponent(item)}/variants/${encodeURIComponent(variant)}`

export const getBank = (offeringId: string) => call<Bank>(base(offeringId))

export const setVariantStatus = (offeringId: string, itemId: string, variantId: string, status: VariantStatus) =>
  call<BankVariant>(`${variantPath(offeringId, itemId, variantId)}/status`, {
    method: 'POST',
    body: JSON.stringify({ status }),
  })

export const editVariant = (offeringId: string, itemId: string, variantId: string, changes: Record<string, unknown>) =>
  call<BankVariant>(variantPath(offeringId, itemId, variantId), { method: 'PATCH', body: JSON.stringify(changes) })

export const approvePending = (offeringId: string, itemIds?: string[]) =>
  call<{ approved: number }>(`${base(offeringId)}/approve-pending`, {
    method: 'POST',
    body: JSON.stringify(itemIds ? { item_ids: itemIds } : {}),
  })
