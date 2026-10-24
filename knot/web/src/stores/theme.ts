/**
 * Your palette: just yours (the other person picks their own). Saved on this phone instantly,
 * and to your account a moment later, so it follows you to another phone.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/lib/api'
import {
  applyTheme,
  DEFAULT_THEME,
  fromServerTheme,
  loadLocalTheme,
  PRESETS,
  saveLocalTheme,
  toServerTheme,
  type Mode,
  type ThemePrefs,
} from '@/lib/theme'

export const useTheme = defineStore('theme', () => {
  const prefs = ref<ThemePrefs>(loadLocalTheme())
  const deep = ref(false)
  let saveTimer: ReturnType<typeof setTimeout> | undefined

  function paint() {
    applyTheme(prefs.value, deep.value)
  }

  function set(next: ThemePrefs, { sync = true } = {}) {
    prefs.value = next
    saveLocalTheme(next)
    paint()
    if (sync) {
      // The slider fires constantly while dragging: save once it settles.
      clearTimeout(saveTimer)
      saveTimer = setTimeout(() => {
        api.patch('/me', { theme: toServerTheme(prefs.value) }).catch(() => {
          /* kept locally; retried on the next change */
        })
      }, 600)
    }
  }

  const setMode = (mode: Mode) => set({ ...prefs.value, mode })
  const setPreset = (id: string) => {
    const p = PRESETS.find((x) => x.id === id)
    if (p) set({ ...prefs.value, preset: p.id, baseHue: p.base, accentHue: p.accent })
  }
  const setAccent = (hue: number) => set({ ...prefs.value, preset: 'custom', accentHue: hue })

  /** Deep dims and slows whatever palette is active (home and the game screens only). */
  function setDeep(on: boolean) {
    if (deep.value === on) return
    deep.value = on
    paint()
  }

  /** After sign-in: the account's saved theme wins over this phone's. */
  function adoptServer(theme: Parameters<typeof fromServerTheme>[0]) {
    const t = fromServerTheme(theme)
    if (t) set(t, { sync: false })
    else if (JSON.stringify(prefs.value) !== JSON.stringify(DEFAULT_THEME)) set(prefs.value) // push this phone's choice up
  }

  return { prefs, deep, setMode, setPreset, setAccent, setDeep, adoptServer, paint }
})
