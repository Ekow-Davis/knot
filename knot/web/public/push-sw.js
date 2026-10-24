/* Notifications, loaded into the service worker (see workbox.importScripts in vite.config.ts).
 * Plain JS on purpose: it runs inside the service worker, outside the app's build. */

self.addEventListener('push', (event) => {
  let d = {}
  try {
    d = event.data ? event.data.json() : {}
  } catch (e) {
    d = {}
  }
  event.waitUntil(
    self.registration.showNotification(d.title || 'W.W.', {
      body: d.body || '',
      tag: d.tag || undefined, // a newer tug replaces an older one instead of stacking
      renotify: !!d.tag,
      icon: '/icons/icon-192.png',
      badge: '/icons/favicon-32.png',
      data: { url: d.url || '/' },
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = new URL((event.notification.data && event.notification.data.url) || '/', self.location.origin).href
  event.waitUntil(
    (async () => {
      const open = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      for (const c of open) {
        if ('focus' in c) {
          await c.focus()
          if ('navigate' in c) {
            try {
              await c.navigate(url)
            } catch (e) {
              /* some browsers refuse; focusing is enough */
            }
          }
          return
        }
      }
      await self.clients.openWindow(url)
    })(),
  )
})
