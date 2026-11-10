import type { Scene } from '../contracts'
import { cleaningScene } from './cleaning'
import { forcesScene } from './forces'
import { galvanicScene } from './galvanic'
import { titrationScene } from './titration'

/**
 * Prepared scenes, standing in for scenes the model will generate from the
 * student's prompt. `match` plays the part of that generation in the mock.
 */
export const demoScenes: { scene: Scene; prompt: { label: string; text: string }; match: RegExp }[] = [
  {
    scene: cleaningScene,
    prompt: { label: 'Why is my average too high?', text: 'This data-cleaning code gives an average that looks too high. Why?' },
    match: /average|code|clean|python|平均|代码/i,
  },
  {
    scene: forcesScene,
    prompt: { label: 'When do two atoms balance?', text: 'How close do two atoms get before the force between them balances?' },
    match: /atom|molecul|force|distance|分子|原子|作用力/i,
  },
  {
    scene: galvanicScene,
    prompt: { label: 'Build a galvanic cell', text: "Why does a galvanic cell need a salt bridge? I'd like to build one." },
    match: /galvanic|salt bridge|electrochem|cell potential|voltmeter|原电池|盐桥|电化学/i,
  },
  {
    scene: titrationScene,
    prompt: { label: 'Practise a titration lab', text: 'I have a titration lab tomorrow: standardising NaOH with HCl. Can I practise?' },
    match: /titrat|burette|lab|滴定|实验/i,
  },
]

export { cleaningScene, forcesScene, galvanicScene, titrationScene }
export { mockAsk, prepareScene } from './mockModel'
