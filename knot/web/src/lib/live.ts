/**
 * The live connection (/api/ws). One per open app.
 *
 * iOS suspends web apps in the background and kills their sockets, so this reconnects:
 * immediately when the app comes back to the foreground or the network returns, otherwise
 * with backoff (1s, 2s, 4s … up to 30s). Every (re)connect starts with a "hello", which the
 * stores treat as "re-fetch everything", so nothing missed while away stays missed.
 */
import { ref } from 'vue'

export type LiveMessage =
  | { type: 'hello'; partner_online: boolean }
  | { type: 'presence'; online: boolean }
  | { type: 'settings'; settings: import('./types').SharedSettings; by: string }
  | { type: 'spicy'; user_id: string; on: boolean }
  | { type: 'profile'; user_id: string; display_name: string | null; theme: import('./types').Theme }
  | { type: 'knot'; key_version: number; by: string }
  | { type: 'pair'; complete: boolean }
  | { type: 'closed'; code: number }
  // Game events (round.drawn, round.sealed, round.hold, round.pull, round.revealed,
  // round.passed, round.verdict, round.expired) and tugs: handled by stores/round.ts.
  | { type: `round.${string}` | 'tug'; [k: string]: unknown }

type Handler = (msg: LiveMessage) => void

export const liveState = ref<'off' | 'connecting' | 'open'>('off')

const handlers = new Set<Handler>()
let ws: WebSocket | null = null
let wanted = false
let attempt = 0
let retryTimer: ReturnType<typeof setTimeout> | undefined
let pingTimer: ReturnType<typeof setInterval> | undefined
let onExpired: (() => void) | null = null

export function onLive(h: Handler): () => void {
  handlers.add(h)
  return () => handlers.delete(h)
}

export function setLiveExpiredHandler(fn: () => void) {
  onExpired = fn
}

function emit(msg: LiveMessage) {
  for (const h of handlers) {
    try {
      h(msg)
    } catch (e) {
      console.error('live handler failed', e)
    }
  }
}

function connect() {
  if (!wanted || ws) return
  clearTimeout(retryTimer)
  const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/ws`
  liveState.value = 'connecting'
  const sock = new WebSocket(url)
  ws = sock

  sock.onopen = () => {
    attempt = 0
    liveState.value = 'open'
    clearInterval(pingTimer)
    // Keeps proxies (and Railway) from closing an idle connection.
    pingTimer = setInterval(() => sock.readyState === WebSocket.OPEN && sock.send('{"type":"ping"}'), 25_000)
  }

  sock.onmessage = (e) => {
    let msg: { type?: string }
    try {
      msg = JSON.parse(e.data)
    } catch {
      return
    }
    if (msg.type && msg.type !== 'pong') emit(msg as LiveMessage)
  }

  sock.onclose = (e) => {
    if (ws === sock) ws = null
    clearInterval(pingTimer)
    liveState.value = 'off'
    emit({ type: 'closed', code: e.code })
    if (e.code === 4401) {
      // The session ended: no point retrying until they sign in again.
      wanted = false
      onExpired?.()
      return
    }
    if (wanted) {
      const delay = Math.min(30_000, 1000 * 2 ** attempt++)
      retryTimer = setTimeout(connect, delay)
    }
  }
}

export function startLive() {
  wanted = true
  connect()
}

export function stopLive() {
  wanted = false
  clearTimeout(retryTimer)
  clearInterval(pingTimer)
  const sock = ws
  ws = null
  sock?.close(1000)
  liveState.value = 'off'
}

function reconnectNow() {
  if (!wanted) return
  attempt = 0
  if (ws && ws.readyState === WebSocket.OPEN) return
  if (ws && ws.readyState === WebSocket.CONNECTING) return
  ws = null
  connect()
}

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') reconnectNow()
})
window.addEventListener('online', reconnectNow)
window.addEventListener('pageshow', reconnectNow)
