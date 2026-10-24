import { createRouter, createWebHistory } from 'vue-router'
import { isStandalone } from '@/lib/platform'
import { useAuth } from '@/stores/auth'
import { useKnot } from '@/stores/knot'

declare module 'vue-router' {
  interface RouteMeta {
    /** Must be signed in. */
    auth?: boolean
    /** Only for people who aren't signed in (the sign-in screens). */
    guest?: boolean
    /** Which part of the sign-in flow must already be done to be here. */
    needs?: 'email' | 'ticket' | 'pairing'
    /** Needs the knot open on this phone (phrase entered or remembered). */
    knot?: boolean
  }
}

/**
 * Opened in a browser → landing page (what it is + how to install).
 * Opened from the home screen → straight to the door (sign in) or home (already signed in).
 */
export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'landing',
      component: () => import('@/views/LandingView.vue'),
      beforeEnter: () => (isStandalone() ? { name: 'door' } : true),
    },
    { path: '/door', name: 'door', component: () => import('@/views/DoorView.vue'), meta: { guest: true } },
    {
      path: '/signin/email',
      name: 'email',
      component: () => import('@/views/signin/EmailView.vue'),
      meta: { guest: true },
    },
    {
      path: '/signin/code',
      name: 'code',
      component: () => import('@/views/signin/CodeView.vue'),
      meta: { guest: true, needs: 'email' },
    },
    {
      path: '/signin/pair',
      name: 'pair',
      component: () => import('@/views/signin/PairView.vue'),
      meta: { guest: true, needs: 'ticket' },
    },
    {
      path: '/signin/name',
      name: 'name',
      component: () => import('@/views/signin/NameView.vue'),
      meta: { guest: true, needs: 'pairing' },
    },
    { path: '/away', name: 'away', component: () => import('@/views/signin/AwayView.vue') },
    { path: '/unlock', name: 'unlock', component: () => import('@/views/UnlockView.vue'), meta: { auth: true } },
    {
      path: '/home',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: { auth: true, knot: true },
    },
    {
      path: '/play',
      name: 'play',
      component: () => import('@/views/PlayView.vue'),
      meta: { auth: true, knot: true },
    },
    {
      path: '/tonight',
      name: 'tonight',
      component: () => import('@/views/TonightView.vue'),
      meta: { auth: true, knot: true },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: { auth: true, knot: true },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuth()
  if (auth.status === 'unknown' && (to.meta.auth || to.meta.guest)) await auth.load()

  const signedIn = auth.status === 'signed_in'
  if (to.meta.auth && !signedIn) return { name: auth.status === 'expired' ? 'away' : 'door' }
  if (to.meta.guest && signedIn) return { name: 'home' }

  // The knot: home needs it open; the unlock screen is only for when it isn't (or to change it).
  if (signedIn && (to.meta.knot || to.name === 'unlock')) {
    const knot = useKnot()
    if (knot.status === 'unknown') {
      try {
        await knot.load()
      } catch {
        // Offline on launch: let the screen show its own offline state rather than loop.
        if (to.meta.knot) return true
      }
    }
    const open = knot.status === 'unlocked'
    if (to.meta.knot && !open) return { name: 'unlock' }
    if (to.name === 'unlock' && open && to.query.mode !== 'change') return { name: 'home' }
  }

  // Deep links into the middle of sign-in (or a refresh halfway through) restart from the email step.
  const f = auth.flow
  if (to.meta.needs === 'email' && !f.email) return { name: 'email' }
  if (to.meta.needs === 'ticket' && !f.ticket) return { name: 'email' }
  if (to.meta.needs === 'pairing' && (!f.ticket || (f.kind === 'needs_pairing' && !f.invite)))
    return { name: f.ticket ? 'pair' : 'email' }
  return true
})

router.afterEach(() => {
  // The static <title> stays "W.W." for link previews; inside, it's Knot.
  document.title = 'Knot'
})
