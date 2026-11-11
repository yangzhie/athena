/**
 * Each unit gets its own ink colour, like coloured index tabs in a notebook.
 * Stable per unit code; chosen to read well on both paper and dark backgrounds.
 */
const INKS = ['#2f7f7a', '#c0563f', '#7a4f9a', '#3f6fb0', '#8a7a2a', '#b0476e', '#4f7f3a']

export function unitColor(code: string): string {
  let h = 0
  for (const ch of code) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return INKS[h % INKS.length]
}
