/**
 * The home screen's shared state. Every tap updates this phone immediately (optimistic),
 * then the server; if the server says no, it snaps back. Changes from the other phone arrive
 * over the live connection and show as a short activity line ("Ama changed depth to Deep").
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, ApiError } from '@/lib/api'
import { toast } from '@/lib/toast'
import type { Category, Depth, HatCategory, HomeOut, SharedSettings } from '@/lib/types'
import { useAuth } from './auth'

export const CATEGORIES: { id: Category; label: string }[] = [
  { id: 'cozy', label: 'Cozy' },
  { id: 'silly', label: 'Silly' },
  { id: 'sweet', label: 'Sweet' },
  { id: 'spicy', label: 'Spicy' },
  { id: 'big', label: 'Big questions' },
  { id: 'memories', label: 'Memories' },
  { id: 'future', label: 'Future' },
]
export const HAT: HatCategory[] = ['cozy', 'silly', 'sweet', 'big', 'memories', 'future']
export const DEPTHS: { id: Depth; label: string }[] = [
  { id: 'light', label: 'Light' },
  { id: 'medium', label: 'Medium' },
  { id: 'deep', label: 'Deep' },
]
const label = (id: string) => CATEGORIES.find((c) => c.id === id)?.label ?? id
const depthLabel = (id: string) => DEPTHS.find((d) => d.id === id)?.label ?? id

const DEFAULT: SharedSettings = { depth: 'light', categories: ['cozy', 'silly', 'sweet'], random: false, excluded: [] }

export const useHome = defineStore('home', () => {
  const settings = ref<SharedSettings>({ ...DEFAULT })
  const spicyMe = ref(false)
  const spicyThem = ref(false)
  const turnUserId = ref<string | null>(null)
  const partnerOnline = ref(false)
  const loaded = ref(false)
  /** "I'm ready" for the next card (both here). Cleared when a card is dealt. */
  const readyMe = ref(false)
  const readyThem = ref(false)
  /** Which screen they're on: 'play' (at the table), 'home', 'settings'… or '' if unknown/away. */
  const partnerWhere = ref('')

  /** The line under the avatars: what the other person just did. Clears itself. */
  const activity = ref('')
  /** A chip that just changed on the other phone gets a brief ring. */
  const flash = ref<Category | null>(null)
  let activityTimer: ReturnType<typeof setTimeout> | undefined

  const auth = useAuth()
  const partner = computed(() => auth.me?.partner?.display_name ?? 'They')
  const myTurn = computed(() => !turnUserId.value || turnUserId.value === auth.me?.id)

  const spicyState = computed<'both' | 'waiting' | 'theirs' | 'off'>(() =>
    spicyMe.value && spicyThem.value ? 'both' : spicyMe.value ? 'waiting' : spicyThem.value ? 'theirs' : 'off',
  )

  /** Mirror of api/app/mix.py: what a draw can actually pick from. */
  const inPlay = computed<Category[]>(() => {
    const s = settings.value
    const ids: Category[] = s.random ? HAT.filter((c) => !s.excluded.includes(c)) : HAT.filter((c) => s.categories.includes(c))
    if (spicyState.value === 'both') ids.push('spicy')
    return ids
  })

  const summary = computed(() => {
    const s = settings.value
    if (s.random) {
      const no: string[] = HAT.filter((c) => s.excluded.includes(c)).map(label)
      if (spicyState.value !== 'both') no.push('Spicy')
      return no.length ? `Random, but no ${no.join(', ')}.` : 'Random. Anything goes.'
    }
    const list = inPlay.value.map(label).join(', ')
    const wait = spicyState.value === 'waiting' ? ` Spicy waits until ${partner.value} says yes too.` : ''
    return `Drawing from ${list}.${wait}`
  })

  function say(text: string, chip: Category | null = null) {
    clearTimeout(activityTimer)
    activity.value = text
    flash.value = chip
    activityTimer = setTimeout(() => {
      activity.value = ''
      flash.value = null
    }, 3800)
  }

  function accept(h: HomeOut) {
    settings.value = h.settings
    spicyMe.value = h.spicy_me
    spicyThem.value = h.spicy_them
    turnUserId.value = h.turn_user_id
    partnerOnline.value = h.partner_online
    readyMe.value = h.ready_me
    readyThem.value = h.ready_them
    loaded.value = true
  }

  async function load() {
    try {
      accept(await api.get<HomeOut>('/home'))
    } catch (e) {
      if (!(e instanceof ApiError && e.code === 'offline')) throw e
    }
  }

  // ── Changes from this phone ──

  async function change(patch: Partial<SharedSettings>) {
    const before = settings.value
    settings.value = { ...before, ...patch }
    try {
      settings.value = await api.patch<SharedSettings>('/settings', patch)
    } catch (e) {
      settings.value = before
      toast(e instanceof ApiError && e.code === 'empty_hat' ? 'Keep at least one in the hat.' : 'That didn’t save. Try again.')
    }
  }

  function setDepth(d: Depth) {
    if (d === settings.value.depth) return
    if (d === 'deep') toast('Going deep. Slow down together.')
    change({ depth: d })
  }

  function toggleRandom() {
    change({ random: !settings.value.random, excluded: [] })
  }

  async function toggleSpicy() {
    const on = !spicyMe.value
    spicyMe.value = on
    try {
      await api.put('/me/spicy', { on })
    } catch {
      spicyMe.value = !on
      toast('That didn’t save. Try again.')
    }
  }

  function tapCategory(id: Category) {
    if (id === 'spicy') return toggleSpicy()
    const s = settings.value
    if (s.random) {
      const out = s.excluded.includes(id)
      if (!out && s.excluded.length >= HAT.length - 1) return toast('Keep at least one in the hat.')
      return change({ excluded: out ? s.excluded.filter((x) => x !== id) : [...s.excluded, id] })
    }
    const on = s.categories.includes(id)
    if (on && s.categories.length <= 1) return toast('Keep at least one in the hat.')
    change({ categories: on ? s.categories.filter((x) => x !== id) : [...s.categories, id] })
  }

  // ── Changes from the other phone ──

  function remoteSettings(next: SharedSettings, by: string) {
    const prev = settings.value
    settings.value = next
    if (by === auth.me?.id) return // an echo of our own change (maybe from another tab)
    const P = partner.value
    if (next.depth !== prev.depth) return say(`${P} changed depth to ${depthLabel(next.depth)}`)
    if (next.random !== prev.random) return say(`${P} turned Random ${next.random ? 'on' : 'off'}`)
    const added = (a: string[], b: string[]) => a.find((x) => !b.includes(x)) as HatCategory | undefined
    let c: HatCategory | undefined
    if ((c = added(next.categories, prev.categories))) return say(`${P} added ${label(c)}`, c)
    if ((c = added(prev.categories, next.categories))) return say(`${P} took out ${label(c)}`, c)
    if ((c = added(next.excluded, prev.excluded))) return say(`${P} left out ${label(c)}`, c)
    if ((c = added(prev.excluded, next.excluded))) return say(`${P} put ${label(c)} back`, c)
  }

  function remoteSpicy(userId: string, on: boolean) {
    if (userId === auth.me?.id) {
      spicyMe.value = on
      return
    }
    spicyThem.value = on
    const P = partner.value
    say(on ? `${P} turned Spicy on${spicyMe.value ? ' too' : ''}` : `${P} turned Spicy off`, 'spicy')
  }

  function setPresence(online: boolean) {
    partnerOnline.value = online
    if (!online) {
      readyThem.value = false
      partnerWhere.value = ''
    }
  }

  function remoteReady(on: boolean) {
    readyThem.value = on
    if (on && !readyMe.value) say(`${partner.value} is ready`)
  }

  function clearReady() {
    readyMe.value = readyThem.value = false
  }

  function reset() {
    settings.value = { ...DEFAULT }
    spicyMe.value = spicyThem.value = partnerOnline.value = loaded.value = false
    readyMe.value = readyThem.value = false
    turnUserId.value = null
    activity.value = ''
    flash.value = null
  }

  return {
    settings,
    spicyMe,
    spicyThem,
    spicyState,
    turnUserId,
    myTurn,
    partnerOnline,
    readyMe,
    readyThem,
    partnerWhere,
    loaded,
    activity,
    flash,
    inPlay,
    summary,
    load,
    setDepth,
    toggleRandom,
    tapCategory,
    remoteSettings,
    remoteSpicy,
    setPresence,
    remoteReady,
    clearReady,
    say,
    reset,
  }
})
