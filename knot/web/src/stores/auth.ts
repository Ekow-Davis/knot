/**
 * Who's signed in, plus the in-progress sign-in flow (email → code → pairing → name).
 * The flow lives only in memory: if the app is closed halfway, you simply start again.
 */
import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'
import { api, ApiError } from '@/lib/api'
import type { Me, VerifyResult } from '@/lib/types'
import { useKnot } from './knot'
import { disablePush } from '@/lib/push'

type Status = 'unknown' | 'signed_out' | 'expired' | 'signed_in'

export const useAuth = defineStore('auth', () => {
  const me = ref<Me | null>(null)
  const status = ref<Status>('unknown')

  const flow = reactive({
    email: '',
    resendAfter: 60,
    ticket: null as string | null,
    kind: null as 'new_owner' | 'needs_pairing' | null,
    invite: '',
  })

  const partnerName = computed(() => me.value?.partner?.display_name ?? 'them')

  function resetFlow() {
    Object.assign(flow, { email: '', resendAfter: 60, ticket: null, kind: null, invite: '' })
  }

  function signedIn(user: Me) {
    me.value = user
    status.value = 'signed_in'
    resetFlow()
  }

  /** Ask the server who we are. Called once by the router on first navigation. */
  async function load() {
    try {
      signedIn(await api.get<Me>('/auth/me'))
    } catch (e) {
      me.value = null
      if (e instanceof ApiError && e.code === 'session_expired') status.value = 'expired'
      else if (e instanceof ApiError && e.code === 'offline') status.value = 'unknown'
      else status.value = 'signed_out'
    }
  }

  async function requestCode(email: string) {
    const r = await api.post<{ resend_after: number }>('/auth/code', { email })
    flow.email = email.trim()
    flow.resendAfter = r.resend_after
  }

  async function verify(code: string): Promise<VerifyResult['status']> {
    const r = await api.post<VerifyResult>('/auth/verify', { email: flow.email, code })
    if (r.status === 'signed_in' && r.me) {
      signedIn(r.me)
    } else {
      flow.ticket = r.ticket
      flow.kind = r.status as 'new_owner' | 'needs_pairing'
    }
    return r.status
  }

  async function checkInvite(code: string) {
    await api.post('/auth/check-invite', { ticket: flow.ticket, invite_code: code })
    flow.invite = code
  }

  async function join(displayName: string) {
    const user = await api.post<Me>('/auth/join', {
      ticket: flow.ticket,
      display_name: displayName,
      invite_code: flow.kind === 'needs_pairing' ? flow.invite : null,
    })
    signedIn(user)
  }

  async function updateMe(patch: Partial<Pick<Me, 'display_name' | 'theme'>>) {
    me.value = await api.patch<Me>('/me', patch)
  }

  async function logout() {
    try {
      // This phone shouldn't keep getting notifications meant for whoever signed out.
      await disablePush().catch(() => {})
      await api.post('/auth/logout')
    } finally {
      // Signing out also takes the knot key off this phone.
      const knot = useKnot()
      await knot.forget()
      knot.reset()
      me.value = null
      status.value = 'signed_out'
      resetFlow()
    }
  }

  /** Any API call that comes back 401 mid-use lands here (see router.ts). */
  function markExpired() {
    me.value = null
    status.value = 'expired'
  }

  return {
    me,
    status,
    flow,
    partnerName,
    load,
    requestCode,
    verify,
    checkInvite,
    join,
    updateMe,
    logout,
    resetFlow,
    markExpired,
  }
})
