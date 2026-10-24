/**
 * Knot state for this phone: is there a knot yet, and is it open here?
 *
 *   untied   → nobody has chosen a phrase yet ("Tie the knot.")
 *   locked   → there's a knot, but this phone doesn't hold the key (enter the phrase)
 *   unlocked → key in memory (and in IndexedDB if "remember" was on)
 */
import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'
import { api, ApiError } from '@/lib/api'
import { createKnot, keyFits, openKnot, type KnotRecord } from '@/lib/knot'
import { clearKey, loadKey, saveKey } from '@/lib/keystore'
import { useAuth } from './auth'

interface KnotOut extends Partial<KnotRecord> {
  tied: boolean
  key_version: number
}

type Status = 'unknown' | 'untied' | 'locked' | 'unlocked'

export class PhraseMismatch extends Error {}
export class AlreadyTied extends Error {}

export const useKnot = defineStore('knot', () => {
  const status = ref<Status>('unknown')
  const version = ref(0)
  /** The other phone changed the phrase since this one last had it. */
  const changedElsewhere = ref(false)
  const record = shallowRef<KnotRecord | null>(null)
  // shallowRef: Vue must not wrap the CryptoKey in a reactive proxy.
  const key = shallowRef<CryptoKey | null>(null)

  function accept(out: KnotOut) {
    version.value = out.key_version
    record.value = out.tied ? (out as KnotRecord) : null
  }

  async function remember(k: CryptoKey, on: boolean) {
    const userId = useAuth().me?.id
    if (on && userId) await saveKey({ key: k, version: version.value, userId })
    else await clearKey()
  }

  /** Called by the router before any screen that needs the knot. */
  async function load() {
    const out = await api.get<KnotOut>('/knot')
    accept(out)
    if (!out.tied) {
      key.value = null
      status.value = 'untied'
      return
    }
    // Already open in memory, for this version?
    if (key.value && (await keyFits(key.value, record.value!))) {
      status.value = 'unlocked'
      return
    }
    // Remembered on this phone?
    const stored = await loadKey()
    const myId = useAuth().me?.id
    if (stored && stored.userId === myId) {
      if (stored.version === out.key_version && (await keyFits(stored.key, record.value!))) {
        key.value = stored.key
        status.value = 'unlocked'
        return
      }
      // A key from an older phrase: the other phone retied.
      changedElsewhere.value = stored.version < out.key_version
      await clearKey()
    }
    key.value = null
    status.value = 'locked'
  }

  async function tie(phrase: string, rememberOnPhone: boolean) {
    const made = await createKnot(phrase)
    try {
      accept(await api.post<KnotOut>('/knot', made.record))
    } catch (e) {
      if (e instanceof ApiError && e.code === 'already_tied') {
        // They got there first: switch to entering the phrase they chose.
        accept(e.extra.knot as KnotOut)
        status.value = 'locked'
        throw new AlreadyTied()
      }
      throw e
    }
    key.value = made.key
    status.value = 'unlocked'
    await remember(made.key, rememberOnPhone)
  }

  async function unlock(phrase: string, rememberOnPhone: boolean) {
    if (!record.value) await load()
    const k = await openKnot(phrase, record.value!)
    if (!k) throw new PhraseMismatch()
    key.value = k
    status.value = 'unlocked'
    changedElsewhere.value = false
    await remember(k, rememberOnPhone)
  }

  async function retie(phrase: string) {
    const made = await createKnot(phrase)
    accept(await api.put<KnotOut>('/knot', { ...made.record, expected_version: version.value }))
    key.value = made.key
    status.value = 'unlocked'
    // Keep the "remember" choice this phone already had.
    const wasRemembered = (await loadKey()) !== null
    await remember(made.key, wasRemembered)
  }

  /** Lock this phone: drop the key from memory and storage. */
  async function forget() {
    key.value = null
    await clearKey()
    if (status.value === 'unlocked') status.value = 'locked'
  }

  /**
   * The other phone tied or retied. Returns true when this phone now needs the phrase
   * (the caller sends it to the unlock screen).
   */
  async function remoteChange(newVersion: number, by: string): Promise<boolean> {
    if (by === useAuth().me?.id) return false // our own change, from this or another tab
    if (newVersion <= version.value && status.value !== 'untied') return false
    const wasTied = status.value !== 'untied'
    key.value = null
    await clearKey()
    await load() // picks up the new salt and check value; status becomes 'locked'
    changedElsewhere.value = wasTied
    return status.value !== 'unlocked'
  }

  function reset() {
    key.value = null
    record.value = null
    status.value = 'unknown'
    changedElsewhere.value = false
  }

  return { status, version, changedElsewhere, key, load, tie, unlock, retie, forget, reset, remoteChange }
})
