/**
 * Makes every icon and the link-preview card from ONE emblem image.
 *
 *   1. Put your emblem at  web/brand/emblem.png   (square-ish PNG with a transparent background,
 *      ideally 1024px or larger)
 *   2. npm run make:brand
 *        optional:  -- --bg "#1d3b8f" --caption "A project series to the one I love"
 *
 * Any empty (transparent) margin around the emblem is trimmed off first, so it fills the icons.
 * If the emblem has its own solid background, the app icons use it edge to edge; if it's
 * transparent, it sits large on --bg.
 *
 * Writes into web/public:
 *   icons/apple-touch-icon.png   180×180  iPhone Home Screen (no transparency: iOS would fill it black)
 *   icons/icon-192.png           192×192
 *   icons/icon-512.png           512×512
 *   icons/icon-512-maskable.png  512×512  emblem kept inside Android's safe circle
 *   icons/favicon-32.png         32×32    browser tab: just the emblem, transparent
 *   icons/favicon-180.png        180×180  sharper tab icon on high-density screens
 *   og.png                      1200×630  the card shown when the link is pasted into a chat
 */
import { existsSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import sharp from 'sharp'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const args = Object.fromEntries(
  process.argv
    .slice(2)
    .join(' ')
    .split(/--(?=\w)/)
    .filter(Boolean)
    .map((s) => {
      const [k, ...v] = s.trim().split(' ')
      return [k, v.join(' ').replace(/^"|"$/g, '')]
    }),
)

const BG = args.bg || '#1d3b8f' // deep blue
const CAPTION = args.caption || 'A project series to the one I love'
const EMBLEM = join(root, 'brand', 'emblem.png')
const OUT = join(root, 'public')

if (!existsSync(EMBLEM)) {
  console.error(`Put your emblem at ${EMBLEM} first (PNG, transparent background).`)
  process.exit(1)
}
mkdirSync(join(OUT, 'icons'), { recursive: true })

// Trim empty margins so the emblem itself, not its padding, fills the space.
const SOURCE = await sharp(EMBLEM).trim({ threshold: 12 }).png().toBuffer()
const { isOpaque } = await sharp(SOURCE).stats()
const CLEAR = { r: 0, g: 0, b: 0, alpha: 0 }
const fit = (box, mode = 'contain') => sharp(SOURCE).resize(box, box, { fit: mode, background: CLEAR }).toBuffer()

/** An app icon: solid square, emblem as large as it can be. */
async function square(size, emblemShare, file) {
  const emblem = isOpaque ? await fit(size, 'cover') : await fit(Math.round(size * emblemShare))
  await sharp({ create: { width: size, height: size, channels: 4, background: BG } })
    .composite([{ input: emblem, gravity: 'center' }])
    .flatten({ background: BG }) // no transparent pixels anywhere
    .png()
    .toFile(join(OUT, file))
  console.log('  ✓', file)
}

/** The browser-tab icon: just the emblem, filling the square, background left transparent. */
async function favicon(size, file) {
  await sharp(await fit(size, isOpaque ? 'cover' : 'contain'))
    .png()
    .toFile(join(OUT, file))
  console.log('  ✓', file)
}

const escape = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])

async function ogCard() {
  const W = 1200
  const H = 630
  const E = 380
  const emblem = await fit(E)
  // A soft light behind the emblem, and the caption in a serif.
  const overlay = Buffer.from(`
    <svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="g" cx="50%" cy="40%" r="55%">
          <stop offset="0%" stop-color="#ffffff" stop-opacity="0.16"/>
          <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
        </radialGradient>
      </defs>
      <rect width="100%" height="100%" fill="url(#g)"/>
      <text x="50%" y="${H - 70}" text-anchor="middle"
            font-family="Georgia, 'Times New Roman', serif" font-style="italic" font-size="46"
            fill="#ffffff" fill-opacity="0.92">${escape(CAPTION)}</text>
    </svg>`)
  await sharp({ create: { width: W, height: H, channels: 4, background: BG } })
    .composite([
      { input: overlay, top: 0, left: 0 },
      { input: emblem, top: 56, left: Math.round((W - E) / 2) },
    ])
    .flatten({ background: BG })
    .png()
    .toFile(join(OUT, 'og.png'))
  console.log('  ✓ og.png')
}

console.log(`Making icons on ${BG} from brand/emblem.png`)
console.log(isOpaque ? '  (emblem has its own background: used edge to edge)' : '  (transparent emblem: placed large on the background)')
await square(180, 0.86, 'icons/apple-touch-icon.png')
await square(192, 0.86, 'icons/icon-192.png')
await square(512, 0.86, 'icons/icon-512.png')
await square(512, 0.7, 'icons/icon-512-maskable.png') // Android crops to a circle: keep it inside
await favicon(32, 'icons/favicon-32.png')
await favicon(180, 'icons/favicon-180.png')
await ogCard()
console.log('Done. Rebuild (npm run build) or restart npm run dev to pick them up.')
