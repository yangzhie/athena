import { codeGraphModule } from './codeGraph/module'
import { forceLabModule } from './forceLab/module'
import { forceReadoutModule } from './forceReadout/module'
import { halfCellModule } from './halfCell/module'
import { noteModule } from './note/module'
import { potentialLogModule } from './potentialLog/module'
import { resultModule } from './result/module'
import { saltBridgeModule } from './saltBridge/module'
import { titrationModule } from './titration/module'
import { titrationReadoutModule } from './titrationReadout/module'
import type { AnyModule } from './types'
import { voltmeterModule } from './voltmeter/module'

/** The preset object types. The agent picks from these and fills in their config. */
export const presetModules: AnyModule[] = [
  noteModule, codeGraphModule, forceLabModule, forceReadoutModule, titrationModule, titrationReadoutModule, resultModule,
  halfCellModule, saltBridgeModule, voltmeterModule, potentialLogModule]
