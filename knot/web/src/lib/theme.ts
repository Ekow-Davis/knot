/**
 * Theme system, ported from the Knot design.
 *
 * A palette is generated from three inputs: mode (night/candle), base hue (backgrounds) and
 * accent hue (knot + buttons). Lightness and chroma are fixed per token, so contrast holds for
 * any hue. "Deep" isn't a separate palette — it dims and slows whatever palette is active.
 */

export type Mode = 'night' | 'candle'

export interface ThemePrefs {
  mode: Mode
  preset: string // preset id, or 'custom'
  baseHue: number
  accentHue: number
}

export const PRESETS = [
  { id: 'plum', label: 'Plum', base: 340, accent: 38 },
  { id: 'ink', label: 'Ink', base: 265, accent: 300 },
  { id: 'moss', label: 'Moss', base: 150, accent: 115 },
  { id: 'ember', label: 'Ember', base: 30, accent: 55 },
  { id: 'tide', label: 'Tide', base: 225, accent: 190 },
  { id: 'gold', label: 'Gold', base: 300, accent: 85 },
] as const

export const DEFAULT_THEME: ThemePrefs = { mode: 'night', preset: 'plum', baseHue: 340, accentHue: 38 }

const ok = (l: number, c: number, h: number, a?: number) =>
  `oklch(${+l.toFixed(3)} ${+c.toFixed(3)} ${h}${a != null ? ' / ' + a : ''})`

export function palette(mode: Mode, b: number, a: number, deep = false): Record<string, string> {
  const d = deep ? 1 : 0
  const cB = deep ? 0.6 : 1
  const cA = deep ? 0.65 : 1
  const m = deep ? 1.6 : 1

  if (mode === 'night') {
    return {
      '--bg': ok(0.2 - 0.05 * d, 0.045 * cB, b),
      '--bg2': ok(0.145 - 0.04 * d, 0.035 * cB, b),
      '--surface': ok(0.26 - 0.05 * d, 0.045 * cB, b),
      '--surface2': ok(0.31 - 0.05 * d, 0.045 * cB, b),
      '--ink': ok(0.95 - 0.04 * d, 0.012, 80),
      '--muted': ok(0.77 - 0.06 * d, 0.03 * cB, b),
      '--line': ok(0.41 - 0.06 * d, 0.045 * cB, b),
      '--accent': ok(0.79 - 0.07 * d, 0.11 * cA, a),
      '--accent2': ok(0.62 - 0.08 * d, 0.1 * cA, a),
      '--accentInk': ok(0.8 - 0.05 * d, 0.11 * cA, a),
      '--onAccent': ok(0.2, 0.04, b),
      '--glow': ok(0.79, 0.11 * cA, a, deep ? 0.16 : 0.32),
      '--warn': ok(0.75, 0.13, 25),
      '--m': String(m),
    }
  }
  return {
    '--bg': ok(0.965 - 0.07 * d, 0.014 + 0.008 * d, b),
    '--bg2': ok(0.925 - 0.08 * d, 0.025, b),
    '--surface': ok(0.99 - 0.06 * d, 0.007, b),
    '--surface2': ok(0.93 - 0.06 * d, 0.02, b),
    '--ink': ok(0.27, 0.07 * cB, b),
    '--muted': ok(0.46 - 0.04 * d, 0.05 * cB, b),
    '--line': ok(0.85 - 0.06 * d, 0.025, b),
    '--accent': ok(0.7 - 0.08 * d, 0.12 * cA, a),
    '--accent2': ok(0.6 - 0.06 * d, 0.11 * cA, a),
    '--accentInk': ok(0.47 - 0.05 * d, 0.11 * cA, a),
    '--onAccent': ok(0.2, 0.04, b),
    '--glow': ok(0.7, 0.12 * cA, a, deep ? 0.16 : 0.3),
    '--warn': ok(0.5, 0.15, 25),
    '--m': String(m),
  }
}

/** The reveal-card tint for a person's accent hue (their colour on the reveal screen). */
export const tint = (hue: number, mode: Mode) =>
  mode === 'night' ? ok(0.3, 0.06, hue) : ok(0.93, 0.04, hue)

/**
 * OKLCH → #rrggbb. Needed because the <meta name="theme-color"> tag (status bar colour)
 * doesn't reliably accept oklch() on iOS.
 */
export function oklchToHex(l: number, c: number, h: number): string {
  const hr = (h * Math.PI) / 180
  const A = c * Math.cos(hr)
  const B = c * Math.sin(hr)
  const l_ = (l + 0.3963377774 * A + 0.2158037573 * B) ** 3
  const m_ = (l - 0.1055613458 * A - 0.0638541728 * B) ** 3
  const s_ = (l - 0.0894841775 * A - 1.291485548 * B) ** 3
  const lin = [
    4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
    -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
    -0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_,
  ]
  return (
    '#' +
    lin
      .map((x) => {
        const v = x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055
        return Math.round(Math.min(1, Math.max(0, v)) * 255)
          .toString(16)
          .padStart(2, '0')
      })
      .join('')
  )
}

/** Apply a theme to the page: CSS variables on <html>, plus the status-bar colour. */
export function applyTheme(prefs: ThemePrefs, deep = false, root: HTMLElement = document.documentElement) {
  const vars = palette(prefs.mode, prefs.baseHue, prefs.accentHue, deep)
  for (const [k, v] of Object.entries(vars)) root.style.setProperty(k, v)
  root.dataset.mode = prefs.mode

  // Same lightness/chroma as --bg above, converted for the meta tag.
  const d = deep ? 1 : 0
  const hex =
    prefs.mode === 'night'
      ? oklchToHex(0.2 - 0.05 * d, 0.045 * (deep ? 0.6 : 1), prefs.baseHue)
      : oklchToHex(0.965 - 0.07 * d, 0.014 + 0.008 * d, prefs.baseHue)
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', hex)
}

// Per-device fallback until themes are stored on the account (Session 4).
const KEY = 'knot.theme'

export function loadLocalTheme(): ThemePrefs {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) return { ...DEFAULT_THEME, ...JSON.parse(raw) }
  } catch {
    /* private mode or corrupted value: use the default */
  }
  return DEFAULT_THEME
}

export function saveLocalTheme(prefs: ThemePrefs) {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs))
  } catch {
    /* ignore */
  }
}
