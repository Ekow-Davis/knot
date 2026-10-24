import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { applyTheme, loadLocalTheme } from './lib/theme'
import './styles/base.css'

// Paint the right colours before Vue mounts, so there's no flash of the default palette.
applyTheme(loadLocalTheme())

createApp(App).use(createPinia()).use(router).mount('#app')
