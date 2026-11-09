/** Curated sandbox types (design doc, Tier 1). Each is a frontend component with a JSON config. */
export type SandboxType = 'python-runner' | 'subnet-visualiser' | 'molecule-viewer' | 'topology-sim'

/** A sandbox the tutor proposed and the student accepted. Config is validated against the type's schema. */
export interface SandboxSession {
  id: string
  type: SandboxType
  title: string
  config: Record<string, unknown>
  createdAt: string
}
