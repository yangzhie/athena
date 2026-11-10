/** Student-owned session routes; shared lecturer routes deliberately do not use these. */
export const sessionPath = (offeringId: string, sessionId: string) =>
  `/units/${encodeURIComponent(offeringId)}/s/${encodeURIComponent(sessionId)}`

export function playgroundPath(offeringId: string, sessionId: string, sceneId?: string) {
  const path = `${sessionPath(offeringId, sessionId)}/playground`
  return sceneId ? `${path}?scene=${encodeURIComponent(sceneId)}` : path
}
