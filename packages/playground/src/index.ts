/** Public surface of the Playground Canvas. Hosts import from here only. */
export * from './contracts'
export { LearningCanvas } from './LearningCanvas'
export { createPlayground, Playground, type PlaygroundState } from './core/store'
export { componentCatalog, validateScene } from './core/scene'
export { presetModules } from './objects/registry'
export type { CanvasObject, ObjectModule, Runtimes } from './objects/types'
export { simulatedPython } from './runtimes/simulatedPython'
export { describeCall, TutorRunner, type TutorHooks, type TutorMessage, type TutorRequest } from './tutor/runner'
