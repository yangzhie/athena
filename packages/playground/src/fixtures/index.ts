import type { Scene } from '../contracts'
import { bubbleScene } from './bubble'
import { cleaningScene } from './cleaning'
import { forcesScene } from './forces'
import { galvanicScene } from './galvanic'
import { pendulumScene } from './pendulum'
import { photoelectricScene } from './photoelectric'
import { titrationScene } from './titration'

/**
 * Prepared scenes, standing in for scenes the model will generate from the
 * student's prompt. `match` plays the part of that generation in the mock.
 */
export const demoScenes: { scene: Scene; prompt: { label: string; text: string }; match: RegExp }[] = [
  {
    scene: bubbleScene,
    prompt: { label: 'When can bubble sort stop?', text: 'How does bubble sort work, and when can it stop early?' },
    match: /bubble|sort/i,
  },
  {
    scene: pendulumScene,
    prompt: { label: 'Measure g with a pendulum', text: 'How can I measure g with a pendulum, and does the mass matter?' },
    match: /pendulum|swing|measure g|gravity/i,
  },
  {
    scene: photoelectricScene,
    prompt: { label: 'Measure Planck’s constant', text: "How does the photoelectric effect work? I have a lab on measuring Planck's constant." },
    match: /photoelectric|photon|planck|work function|stopping voltage/i,
  },
  {
    scene: cleaningScene,
    prompt: { label: 'Why is my average too high?', text: 'This data-cleaning code gives an average that looks too high. Why?' },
    match: /average|code|clean|python/i,
  },
  {
    scene: forcesScene,
    prompt: { label: 'When do two atoms balance?', text: 'How close do two atoms get before the force between them balances?' },
    match: /atom|molecul|force|distance/i,
  },
  {
    scene: galvanicScene,
    prompt: { label: 'Build a galvanic cell', text: "Why does a galvanic cell need a salt bridge? I'd like to build one." },
    match: /galvanic|salt bridge|electrochem|cell potential|voltmeter/i,
  },
  {
    scene: titrationScene,
    prompt: { label: 'Practise a titration lab', text: 'I have a titration lab tomorrow: standardising NaOH with HCl. Can I practise?' },
    match: /titrat|burette|lab/i,
  },
]

export { bubbleScene, cleaningScene, forcesScene, galvanicScene, pendulumScene, photoelectricScene, titrationScene }
export { mockAsk, prepareScene } from './mockModel'
