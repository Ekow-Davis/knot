/**
 * Connects the pieces that span the whole app:
 *   • open the live connection while signed in, close it when not
 *   • route live messages to the right store
 *   • keep the theme in step with the account, and Deep's dimmer palette on the right screens
 */
import { watch } from 'vue'
import type { Router } from 'vue-router'
import { onLive, setLiveExpiredHandler, startLive, stopLive } from './live'
import { toast } from './toast'
import { useAuth } from '@/stores/auth'
import { useHome } from '@/stores/home'
import { useKnot } from '@/stores/knot'
import { useRound } from '@/stores/round'
import { useTheme } from '@/stores/theme'

/** Screens where a Deep session dims the palette (as in the design). */
const SESSION_SCREENS = new Set(['home', 'play', 'tonight'])

export function wireUp(router: Router) {
  const auth = useAuth()
  const home = useHome()
  const knot = useKnot()
  const theme = useTheme()
  const round = useRound()

  // Live connection follows sign-in.
  watch(
    () => auth.status,
    (s) => {
      if (s === 'signed_in') startLive()
      else {
        stopLive()
        home.reset()
        round.reset()
      }
    },
    { immediate: true },
  )

  // When we learn who we are, adopt the theme saved on the account.
  watch(
    () => auth.me?.id,
    (id) => {
      if (id && auth.me) theme.adoptServer(auth.me.theme)
    },
    { immediate: true },
  )

  // Deep palette only on session screens.
  watch(
    () => [router.currentRoute.value.name, home.settings.depth] as const,
    ([name, depth]) => theme.setDeep(depth === 'deep' && SESSION_SCREENS.has(String(name))),
    { immediate: true },
  )

  setLiveExpiredHandler(() => {
    auth.markExpired()
    router.replace({ name: 'away' })
  })

  onLive(async (msg) => {
    // Everything about the game goes to the round store.
    if (msg.type.startsWith('round.') || msg.type === 'tug') {
      const wasOnHome = router.currentRoute.value.name === 'home'
      await round.onEvent(msg as { type: string; [k: string]: unknown })
      if (msg.type === 'round.drawn' && wasOnHome) toast(`${auth.partnerName} drew one for you both.`)
      if (msg.type === 'round.revealed' || msg.type === 'round.passed') home.load()
      return
    }
    switch (msg.type) {
      case 'hello':
        // Fresh connection (first, or after the phone slept): re-fetch so nothing is missed.
        home.setPresence(msg.partner_online)
        if (auth.me?.pair_complete) {
          home.load()
          round.loadCurrent()
        }
        if (knot.status !== 'unknown') {
          await knot.load().catch(() => {})
          // The phrase may have been changed on the other phone while this one slept.
          const route = router.currentRoute.value
          if (knot.status !== 'unlocked' && route.meta.knot) router.replace({ name: 'unlock' })
        }
        break
      case 'presence':
        home.setPresence(msg.online)
        break
      case 'settings':
        home.remoteSettings(msg.settings, msg.by)
        break
      case 'spicy':
        home.remoteSpicy(msg.user_id, msg.on)
        break
      case 'profile':
        if (auth.me && msg.user_id !== auth.me.id && auth.me.partner) {
          auth.me.partner.display_name = msg.display_name
          auth.me.partner.theme = msg.theme
        }
        break
      case 'pair':
        // She joined while you were looking at the app.
        await auth.load()
        await home.load()
        toast(`${auth.me?.partner?.display_name ?? 'They'} joined. You’re paired.`)
        break
      case 'knot': {
        const needsPhrase = await knot.remoteChange(msg.key_version, msg.by)
        const route = router.currentRoute.value
        if (needsPhrase && route.meta.auth && route.name !== 'unlock') router.replace({ name: 'unlock' })
        break
      }
    }
  })
}
