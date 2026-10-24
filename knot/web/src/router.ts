import { createRouter, createWebHistory } from 'vue-router'
import { isStandalone } from '@/lib/platform'

/**
 * Opened in a browser → landing page (what it is + how to install).
 * Opened from the home screen → straight to the door (sign in / unlock).
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
    {
      path: '/door',
      name: 'door',
      component: () => import('@/views/DoorView.vue'),
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.afterEach(() => {
  // The static <title> stays "W.W." for link previews; inside, it's Knot.
  document.title = 'Knot'
})
