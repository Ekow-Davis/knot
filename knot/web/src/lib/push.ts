/**
 * Notifications on this phone ("tugs").
 *
 * iPhone: only works once the app is on the Home Screen (opened from its icon), over HTTPS,
 * and only after the person taps a button: permission can't be asked for out of nowhere.
 */
import { api } from './api'

export type PushState = 'on' | 'off' | 'denied' | 'unsupported' | 'needs-install'

export function pushSupported(): boolean {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
}

/** On iPhone, push exists only for the installed (Home Screen) app. */
function installedOnIOS(): boolean {
  const ios = /iPhone|iPad|iPod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  if (!ios) return true
  return window.navigator.standalone === true || window.matchMedia('(display-mode: standalone)').matches
}

async function registration(): Promise<ServiceWorkerRegistration | null> {
  if (!('serviceWorker' in navigator)) return null
  // `ready` never settles if no worker is registered, so don't wait forever.
  return Promise.race([
    navigator.serviceWorker.ready,
    new Promise<null>((r) => setTimeout(() => r(null), 3000)),
  ])
}

export async function pushState(): Promise<PushState> {
  if (!installedOnIOS()) return 'needs-install'
  if (!pushSupported()) return 'unsupported'
  if (Notification.permission === 'denied') return 'denied'
  const reg = await registration()
  const sub = await reg?.pushManager.getSubscription()
  return sub && Notification.permission === 'granted' ? 'on' : 'off'
}

function keyBytes(base64url: string): Uint8Array {
  const pad = '='.repeat((4 - (base64url.length % 4)) % 4)
  const raw = atob((base64url + pad).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}

function sameKey(sub: PushSubscription, key: Uint8Array): boolean {
  const have = sub.options?.applicationServerKey
  if (!have) return true // browser doesn't say: assume fine
  const a = new Uint8Array(have)
  return a.length === key.length && a.every((v, i) => v === key[i])
}

/**
 * Subscribe this browser to the server's key. A subscription left over from an older key
 * (e.g. before you generated your VAPID keys) can't receive anything, so it's replaced.
 */
async function subscribeWith(reg: ServiceWorkerRegistration): Promise<PushSubscription> {
  const { key } = await api.get<{ key: string }>('/push/key')
  const bytes = keyBytes(key)
  let sub = await reg.pushManager.getSubscription()
  if (sub && !sameKey(sub, bytes)) {
    await sub.unsubscribe().catch(() => {})
    sub = null
  }
  sub ??= await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: bytes })
  await api.post('/push/subscribe', sub.toJSON())
  return sub
}

/** Must be called from a tap (iOS requires a user gesture for the permission prompt). */
export async function enablePush(): Promise<PushState> {
  if (!installedOnIOS()) return 'needs-install'
  if (!pushSupported()) return 'unsupported'
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') return permission === 'denied' ? 'denied' : 'off'

  const reg = await registration()
  if (!reg) return 'unsupported'
  await subscribeWith(reg)
  return 'on'
}

/**
 * Permission already granted (e.g. allowed in the browser's own settings) but this device never
 * signed up with the server: do that quietly, no prompt needed. Safe to call on every launch.
 */
export async function syncPush(): Promise<void> {
  try {
    if (!installedOnIOS() || !pushSupported() || Notification.permission !== 'granted') return
    const reg = await registration()
    if (!reg) return
    await subscribeWith(reg) // upsert: harmless if already known
  } catch (e) {
    console.warn('[knot] push sync failed', e) // push not set up yet, or offline
  }
}

export async function disablePush(): Promise<void> {
  const reg = await registration()
  const sub = await reg?.pushManager.getSubscription()
  if (!sub) return
  await api.post('/push/unsubscribe', { endpoint: sub.endpoint }).catch(() => {})
  await sub.unsubscribe().catch(() => {})
}

// ── Asking once, at the right moment ──

const ASKED = 'knot.notifyAsked'

/** Show "Can we tug your sleeve?" once: installed, supported, and never answered on this phone. */
export function shouldAskForPush(): boolean {
  if (!installedOnIOS() || !pushSupported()) return false
  if (Notification.permission !== 'default') return false
  try {
    return localStorage.getItem(ASKED) !== '1'
  } catch {
    return false
  }
}

export function markAskedForPush() {
  try {
    localStorage.setItem(ASKED, '1')
  } catch {
    /* ignore */
  }
}
