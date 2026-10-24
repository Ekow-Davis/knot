/** Where are we running? Drives landing page vs app, and which install steps to show. */

export type BrowserKind = 'safari' | 'inapp' | 'android' | 'desktop'

/** True when opened from the home screen (installed PWA). */
export function isStandalone(): boolean {
  if (devForcedApp()) return true
  return window.navigator.standalone === true || window.matchMedia('(display-mode: standalone)').matches
}

/**
 * In-app browsers (WhatsApp, Instagram, Snapchat, Facebook, TikTok…) can't "Add to Home Screen",
 * so the landing page tells her to open the link in Safari first.
 */
export function detectBrowser(ua = navigator.userAgent): BrowserKind {
  const inApp = /FBAN|FBAV|Instagram|Snapchat|WhatsApp|Line\/|TikTok|musical_ly|Twitter|LinkedInApp|GSA\//i
  const isIOS = /iPhone|iPad|iPod/i.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)

  if (inApp.test(ua)) return 'inapp'
  if (isIOS) {
    // Every iOS browser is WebKit, but only Safari's share sheet reliably offers "Add to Home Screen".
    const otherIOSBrowser = /CriOS|FxiOS|EdgiOS|OPiOS/i.test(ua)
    return otherIOSBrowser ? 'inapp' : 'safari'
  }
  if (/Android/i.test(ua)) return 'android'
  return 'desktop'
}

export const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

/**
 * Development only: add ?app=1 to the URL to see the installed-app flow in a normal browser
 * tab (?app=0 turns it off). Remembered for the tab session.
 */
function devForcedApp(): boolean {
  if (!import.meta.env.DEV) return false
  try {
    const flag = new URLSearchParams(location.search).get('app')
    if (flag === '1') sessionStorage.setItem('knot.forceApp', '1')
    if (flag === '0') sessionStorage.removeItem('knot.forceApp')
    return sessionStorage.getItem('knot.forceApp') === '1'
  } catch {
    return false
  }
}
