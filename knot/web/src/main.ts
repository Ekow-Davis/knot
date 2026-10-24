import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { applyTheme, loadLocalTheme } from './lib/theme'
import { setSessionExpiredHandler } from './lib/api'
import { wireUp } from './lib/wiring'
import { captureInstallPrompt } from './lib/platform'
import { useAuth } from './stores/auth'
import './styles/base.css'
import './styles/ui.css'

// Paint the right colours before Vue mounts, so there's no flash of the default palette.
applyTheme(loadLocalTheme())
// Android can offer "Install" before any page is shown; keep the offer for the landing page.
captureInstallPrompt()

const app = createApp(App).use(createPinia()).use(router)

// If the session runs out mid-use, show "You've been away a while."
setSessionExpiredHandler(() => {
  useAuth().markExpired()
  router.replace({ name: 'away' })
})

wireUp(router)
app.mount('#app')
