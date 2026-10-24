import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

// Plum night background from the design. Used for the Android splash and the browser bar
// before the app's own theme takes over at runtime.
const PLUM_BG = '#2b1724'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icons/apple-touch-icon.png', 'og.png', 'push-sw.js'],
      // The service worker also runs in `npm run dev`, so notifications can be tried on localhost.
      devOptions: { enabled: true },
      manifest: {
        // The disguise: what appears under the icon on her home screen.
        name: 'W.W.',
        short_name: 'W.W.',
        description: 'A project series to the one I love',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait',
        background_color: PLUM_BG,
        theme_color: PLUM_BG,
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/icon-512-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // Notification handling lives in public/push-sw.js and is pulled into the generated worker.
        importScripts: ['push-sw.js'],
        navigateFallback: '/index.html',
        // Never let the service worker answer API or WebSocket requests.
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [
          {
            urlPattern: ({ url }) =>
              url.origin === 'https://fonts.googleapis.com' || url.origin === 'https://fonts.gstatic.com',
            handler: 'CacheFirst',
            options: {
              cacheName: 'fonts',
              expiration: { maxEntries: 20, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    // '/src' is resolved from the project root by Vite itself (no Node path helpers needed).
    alias: { '@': '/src' },
  },
  server: {
    // FastAPI runs on :8000 in development; same-origin in production.
    proxy: {
      // 127.0.0.1, not localhost: on Windows "localhost" may try IPv6 first, and uvicorn only listens on IPv4.
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true, ws: true },
    },
  },
})
