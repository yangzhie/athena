/** Boundary schemas derive configurations and supported actions from the real modules. */
import { AGENT_TOOLS } from '../contracts'
import { componentCatalog } from '../core/scene'
import { s } from '../core/schema'
import { presetModules } from '../objects/registry'

export const CATALOG_VERSION = '1.0.0'
const text = s.string()
const number = s.number()
const empty = s.empty()
export const actionSchemas = {
  probe: s.object({ nodeId: text, value: text }),
  editCondition: s.object({ nodeId: text, condition: text }),
  run: empty,
  setDistance: s.object({ distance: s.number(undefined, 0.001, 1000) }),
  moveParticle: s.object({ index: s.integer(undefined, 0, 1), x: number, y: number }),
  setTap: s.object({ opening: s.number(undefined, 0, 1) }),
  dispenseTo: s.object({ volume: s.number(undefined, 0, 10000), mode: s.string(undefined, ['stream', 'dropwise']) }),
  swirl: empty,
  recordEndpoint: empty,
  newTrial: empty,
  dilute: empty,
  refill: empty,
  recordReading: empty,
  swapPlugs: s.object({ plugs: s.array(text, undefined, 2, 2) }),
  // Sort bench
  swap: s.object({ index: s.integer(undefined, 0, 64) }),
  keep: s.object({ index: s.integer(undefined, 0, 64) }),
  finish: empty,
  resetSort: empty,
  // Photoelectric rig and its log
  selectLine: s.object({ index: s.integer(undefined, 0, 16) }),
  setIntensity: s.object({ level: s.number(undefined, 0, 1) }),
  setVoltage: s.object({ volts: s.number(undefined, 0, 100) }),
  recordStop: empty,
  fitLine: empty,
  // Pendulum and its log
  setLength: s.object({ metres: s.number(undefined, 0, 100) }),
  setMass: s.object({ grams: s.number(undefined, 0, 100000) }),
  setAmplitude: s.object({ degrees: s.number(undefined, 0, 90) }),
  recordPeriod: empty,
  fitG: empty,
  // Prediction
  choose: s.object({ option: s.integer(undefined, 0, 16) }),
  // connect has a nullable port reference, checked against the actual port catalogue below.
  connect: s.object({ plug: text }),
}

export function contract() {
  return {
    catalog_version: CATALOG_VERSION,
    capabilities: { durable_actions: true, python: true, traces: false, variable_inspection: false, animation: 'browser-only' },
    components: componentCatalog(presetModules),
    actions: actionSchemas,
    tools: AGENT_TOOLS,
    limits: { objects: 24, actions_per_turn: 24, snapshot_bytes: 65536, source_bytes: 16384 },
    provenance: ['real-run', 'simulated', 'ai-estimate', 'concept', 'material'],
  }
}
