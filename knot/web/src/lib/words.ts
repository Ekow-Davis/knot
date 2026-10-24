/** Small text helpers for the game. */

const ONES = [
  'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
  'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen',
]
const TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']

/** 12 → "Twelve", 34 → "Thirty-four". Past 99, plain digits. */
export function numberWord(n: number): string {
  let w: string
  if (n < 20) w = ONES[n]
  else if (n < 100) w = TENS[Math.floor(n / 10)] + (n % 10 ? '-' + ONES[n % 10] : '')
  else return String(n)
  return w[0].toUpperCase() + w.slice(1)
}

/** "Twelve knots tied." / "One knot tied." */
export const knotsTied = (n: number) => `${numberWord(n)} knot${n === 1 ? '' : 's'} tied.`

// ── Guess auto-match (from the design) ──
// If the guess and the truth share a meaningful word (first 5 letters), it counts as a match
// without asking. Otherwise the person who was guessed about decides "close enough?".

const STOP = new Set(['that', 'with', 'they', 'their', 'obviously', 'probably', 'maybe', 'think', 'would', 'something', 'just', 'really', 'then'])

const words = (s: string) =>
  (s || '')
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, ' ')
    .split(/\s+/)
    .filter((w) => w.length > 3 && !STOP.has(w))

export function closeEnough(guess: string, truth: string): boolean {
  const A = words(guess)
  const B = words(truth)
  return A.some((w) => B.some((v) => v.slice(0, 5) === w.slice(0, 5)))
}

/** Fill in {p} with a name. */
export const fillName = (text: string, name: string) => text.replaceAll('{p}', name)
