/**
 * Where are we running? Drives landing page vs app, and which install steps to show.
 *
 * Install facts this is built on (checked October 2026):
 *  • iOS 26 Safari: Share lives in the ••• menu beside the address bar → Share → Add to Home
 *    Screen (keep "Open as Web App" on). Safari 26 reports "Version/26" but freezes the OS
 *    version at 18_6, so we key off the Safari version, not the OS.
 *  • iOS 18 and earlier Safari: the Share button is in the toolbar.
 *  • iPad: Share is at the top, beside the address bar.
 *  • Chrome / Firefox / Edge on iOS (16.4+) can also Add to Home Screen from their Share menu.
 *  • In-app browsers (Instagram, WhatsApp, Snapchat, Facebook, TikTok…) can't: open in Safari first.
 *  • Android Chrome fires `beforeinstallprompt`, so a real "Install" button is possible.
 */

export type BrowserKind = 'safari' | 'iosother' | 'inapp' | 'android' | 'desktop'

export interface Platform {
  kind: BrowserKind
  /** Safari major version on iOS (26, 18, 17…), or 0 if unknown/not Safari. */
  safari: number
  ipad: boolean
  /** For in-app browsers: which app, when we can tell. */
  app: 'instagram' | 'facebook' | 'snapchat' | 'tiktok' | 'whatsapp' | 'twitter' | 'linkedin' | 'google' | 'other' | null
}

const APPS: [RegExp, NonNullable<Platform['app']>][] = [
  [/Instagram/i, 'instagram'],
  [/FBAN|FBAV|FB_IAB/i, 'facebook'],
  [/Snapchat/i, 'snapchat'],
  [/TikTok|musical_ly|BytedanceWebview/i, 'tiktok'],
  [/WhatsApp/i, 'whatsapp'],
  [/Twitter/i, 'twitter'],
  [/LinkedInApp/i, 'linkedin'],
  [/GSA\//i, 'google'],
  [/Line\/|MicroMessenger|Telegram/i, 'other'],
]

export function detectPlatform(ua = navigator.userAgent, touch = navigator.maxTouchPoints): Platform {
  const ipad = /iPad/i.test(ua) || (/Macintosh/i.test(ua) && touch > 1)
  const ios = ipad || /iPhone|iPod/i.test(ua)
  const app = APPS.find(([re]) => re.test(ua))?.[1] ?? null
  const safari = Number(ua.match(/Version\/(\d+)/)?.[1] ?? 0)

  if (app) return { kind: 'inapp', safari: 0, ipad, app }
  if (ios) {
    if (/CriOS|FxiOS|EdgiOS|OPiOS/i.test(ua)) return { kind: 'iosother', safari: 0, ipad, app: null }
    // Every real Safari says "Safari/"; embedded web views that don't identify themselves usually don't.
    if (!/Safari\//i.test(ua)) return { kind: 'inapp', safari: 0, ipad, app: 'other' }
    return { kind: 'safari', safari, ipad, app: null }
  }
  if (/Android/i.test(ua)) return { kind: 'android', safari: 0, ipad: false, app: null }
  return { kind: 'desktop', safari: 0, ipad: false, app: null }
}

/** Kept for older callers. */
export const detectBrowser = (ua?: string): BrowserKind => detectPlatform(ua).kind

/** True when opened from the home screen (installed PWA), or "open it here" was chosen. */
export function isStandalone(): boolean {
  if (browserAppChosen()) return true
  return window.navigator.standalone === true || window.matchMedia('(display-mode: standalone)').matches
}

export const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

// ── "Open it here instead" (and ?app=1 in development) ──
// Using it in a normal browser tab works, but it isn't the full thing: on iPhone, notifications
// only work once it's on the Home Screen. Remembered for this tab only.

const KEY = 'knot.browserApp'

function browserAppChosen(): boolean {
  try {
    const flag = new URLSearchParams(location.search).get('app')
    if (import.meta.env.DEV && flag === '1') sessionStorage.setItem(KEY, '1')
    if (flag === '0') sessionStorage.removeItem(KEY)
    return sessionStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

export function chooseBrowserApp() {
  try {
    sessionStorage.setItem(KEY, '1')
  } catch {
    /* private mode: they'll just see the landing page again next time */
  }
}

// ── Android: the browser's own install prompt ──

interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

let deferred: InstallPromptEvent | null = null
const listeners = new Set<(available: boolean) => void>()

/** Call once at startup: the event can fire before any page is shown. */
export function captureInstallPrompt() {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault() // we show our own "Install Knot" button instead of the browser's mini-bar
    deferred = e as InstallPromptEvent
    listeners.forEach((l) => l(true))
  })
  window.addEventListener('appinstalled', () => {
    deferred = null
    listeners.forEach((l) => l(false))
  })
}

export function onInstallAvailable(fn: (available: boolean) => void): () => void {
  listeners.add(fn)
  fn(!!deferred)
  return () => listeners.delete(fn)
}

/** Shows the browser's install dialog. Resolves true if they installed. */
export async function promptInstall(): Promise<boolean> {
  if (!deferred) return false
  const e = deferred
  deferred = null
  await e.prompt()
  const { outcome } = await e.userChoice
  listeners.forEach((l) => l(false))
  return outcome === 'accepted'
}
