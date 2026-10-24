/**
 * The game on this phone: the current round, your draft answer, the hold-to-pull state,
 * and the reveal. The server is the source of truth for the round itself, so leaving for
 * Settings (or closing the app) and coming back picks up exactly where you were.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, ApiError } from '@/lib/api'
import { seal as sealText, unseal } from '@/lib/knot'
import { toast } from '@/lib/toast'
import type { AnswerOut, PullOut, QuestionOut, RoundOut } from '@/lib/types'
import { closeEnough } from '@/lib/words'
import { useAuth } from './auth'
import { useHome } from './home'
import { useKnot } from './knot'

/** What's inside an encrypted answer. */
interface AnswerBody {
  t?: string // written answer
  c?: 0 | 1 // would-you-rather choice
}

export interface Revealed {
  roundId: string
  question: QuestionOut
  drawnBy: string
  subjectId: string | null
  mine: AnswerBody | null
  theirs: AnswerBody | null
  /** Guess cards: was it close enough? `auto` = matched without anyone deciding. */
  verdict: 'match' | 'miss' | null
  auto: boolean
}

const TONIGHT_KEY = 'knot.tonight'
function readTonight(): number {
  try {
    return Number(sessionStorage.getItem(TONIGHT_KEY)) || 0
  } catch {
    return 0
  }
}

export const useRound = defineStore('round', () => {
  const auth = useAuth()
  const home = useHome()
  const knot = useKnot()
  const myId = () => auth.me?.id ?? ''

  const round = ref<RoundOut | null>(null)
  const loaded = ref(false)
  const reveal = ref<Revealed | null>(null)
  const passedBy = ref<string | null>(null) // set when the *other* person passed
  const empty = ref(false)
  const expired = ref(false)
  /** Between cards, both at the table: "Ready when you both are." (after a pass, expiry or reshuffle) */
  const between = ref(false)
  const busy = ref(false)

  // Draft answer: kept per round so a trip to Settings doesn't lose it.
  const draftFor = ref<string | null>(null)
  const draft = ref('')
  const choice = ref<0 | 1 | null>(null)

  // Hold-to-pull.
  const partnerHolding = ref(false)
  const partnerPulled = ref(false)
  const iPulled = ref(false)
  const partnerReadAlone = ref(false)

  // "Twelve knots tied." — counted on this phone, for tonight only.
  const tonight = ref(readTonight())
  /** Rounds already read on this phone, so a later reveal (their pull) doesn't pop up again. */
  const readHere = new Set<string>()

  const phase = computed<'none' | 'answer' | 'waiting' | 'reveal' | 'passed' | 'empty' | 'expired' | 'between'>(() => {
    if (reveal.value) return 'reveal'
    if (passedBy.value) return 'passed'
    if (expired.value) return 'expired'
    if (empty.value) return 'empty'
    if (!round.value) return between.value ? 'between' : 'none'
    if (round.value.i_answer && !round.value.i_sealed) return 'answer'
    return 'waiting'
  })

  /** Partner is away: whatever you draw is left sealed for them. */
  const leaving = computed(() => !home.partnerOnline)

  function accept(r: RoundOut | null) {
    round.value = r
    if (r && draftFor.value !== r.id) {
      draftFor.value = r.id
      draft.value = ''
      choice.value = null
      partnerHolding.value = partnerPulled.value = iPulled.value = partnerReadAlone.value = false
    }
    if (r) {
      iPulled.value = r.pulled_by.includes(myId())
      partnerPulled.value = r.pulled_by.some((u) => u !== myId())
    }
  }

  function clearOutcome() {
    reveal.value = null
    passedBy.value = null
    empty.value = false
    expired.value = false
    between.value = false
  }

  /** Leave a pass / expiry / empty hat behind and wait at the table for the next card together. */
  function toBetween() {
    clearOutcome()
    between.value = true
  }

  async function loadCurrent() {
    try {
      const r = await api.get<{ round: RoundOut | null }>('/rounds/current')
      accept(r.round)
    } catch (e) {
      if (!(e instanceof ApiError && e.code === 'offline')) throw e
    } finally {
      loaded.value = true
    }
  }

  async function draw(): Promise<boolean> {
    if (busy.value) return false
    busy.value = true
    clearOutcome()
    try {
      accept(await api.post<RoundOut>('/rounds'))
      return true
    } catch (e) {
      const code = e instanceof ApiError ? e.code : ''
      if (code === 'empty') empty.value = true
      else if (code === 'round_open') await loadCurrent()
      else if (code === 'use_ready') return ready(true)
      else if (code === 'plenty') toast(`That’s plenty waiting for ${auth.partnerName}.`)
      else if (code === 'bank_key_missing') toast('The question bank isn’t set up on the server yet.')
      else toast('Couldn’t draw one. Try again.')
      return code === 'empty' || code === 'round_open'
    } finally {
      busy.value = false
    }
  }

  /**
   * Both here: "I'm ready" (or take it back). When you're both ready, the server deals one
   * card to both phones at once, so this phone gets it in the reply or over the live link.
   */
  async function ready(on: boolean): Promise<boolean> {
    home.readyMe = on
    try {
      const r = await api.post<{ drawn: boolean; empty: boolean; round: RoundOut | null }>('/rounds/ready', {
        ready: on,
      })
      if (r.empty) {
        home.clearReady()
        empty.value = true
        return true
      }
      if (r.drawn && r.round) {
        home.clearReady()
        clearOutcome()
        accept(r.round)
        return true
      }
      return false
    } catch {
      home.readyMe = !on
      toast('That didn’t go through. Try again.')
      return false
    }
  }

  /**
   * "Shuffle them back in". Away: just reshuffle (the caller draws). Both here: reshuffle and
   * count as ready, so their phone shows "Baron shuffled them back in" and one tap deals.
   */
  async function reshuffle() {
    const r = await api.post<{ shuffled_back: number }>('/rounds/reshuffle')
    toast(r.shuffled_back ? 'Shuffled back in.' : 'Nothing to shuffle back yet.')
    if (home.partnerOnline) {
      toBetween()
      await ready(true)
    } else {
      empty.value = false
    }
  }

  async function seal() {
    const r = round.value
    const key = knot.key
    if (!r || !key) return
    const body: AnswerBody = r.question.type === 'wyr' ? { c: choice.value ?? 0 } : { t: draft.value.trim() }
    busy.value = true
    try {
      const s = await sealText(key, JSON.stringify(body), `${r.id}:${myId()}`)
      accept(await api.post<RoundOut>(`/rounds/${r.id}/seal`, { ...s, key_version: knot.version }))
      draft.value = ''
    } catch (e) {
      const code = e instanceof ApiError ? e.code : ''
      if (code === 'stale_key') {
        toast('The phrase changed. Enter the new one to answer.')
        await knot.load()
      } else if (code === 'round_gone') {
        accept(null)
        expired.value = true
      } else toast('That didn’t seal. Try again.')
      throw e
    } finally {
      busy.value = false
    }
  }

  async function pass(retire = false) {
    const r = round.value
    if (!r) return
    await api.post(`/rounds/${r.id}/${retire ? 'retire' : 'pass'}`).catch(() => {})
    accept(null)
    clearOutcome()
    await home.load()
  }

  // ── Holding and pulling ──

  let lastHold = false
  function hold(holding: boolean) {
    const r = round.value
    if (!r || holding === lastHold) return
    lastHold = holding
    api.post(`/rounds/${r.id}/hold`, { holding }).catch(() => {})
  }

  async function pull(alone = false) {
    const r = round.value
    if (!r) return
    iPulled.value = true
    hold(false)
    try {
      const out = await api.post<PullOut>(`/rounds/${r.id}/pull`, { alone })
      if (out.revealed) await showReveal(r.id, out, r)
    } catch (e) {
      iPulled.value = false
      if (e instanceof ApiError && e.code === 'round_gone') {
        accept(null)
        expired.value = true
      } else toast('Couldn’t pull. Try again.')
    }
  }

  async function decode(a: AnswerOut | undefined): Promise<AnswerBody | null> {
    if (!a || !knot.key) return null
    try {
      return JSON.parse(await unseal(knot.key, a.ciphertext, a.nonce, `${roundIdFor.value}:${a.user_id}`))
    } catch {
      return { t: '(sealed under an older phrase)' }
    }
  }
  const roundIdFor = ref('')

  async function showReveal(roundId: string, out: PullOut, r: RoundOut | null) {
    roundIdFor.value = roundId
    const me = myId()
    const mine = await decode(out.answers.find((a) => a.user_id === me))
    const theirs = await decode(out.answers.find((a) => a.user_id !== me))
    const question = out.question ?? r?.question
    if (!question) return
    const subjectId = r?.subject_id ?? null
    let verdict: Revealed['verdict'] = null
    let auto = false
    if (question.type === 'guess' && mine?.t && theirs?.t && closeEnough(mine.t, theirs.t)) {
      verdict = 'match'
      auto = true
    }
    reveal.value = {
      roundId,
      question,
      drawnBy: r?.drawn_by ?? '',
      subjectId,
      mine,
      theirs,
      verdict,
      auto,
    }
    round.value = null
    if (out.turn_user_id) home.turnUserId = out.turn_user_id
    if (!readHere.has(roundId)) {
      readHere.add(roundId)
      tonight.value++
      try {
        sessionStorage.setItem(TONIGHT_KEY, String(tonight.value))
      } catch {
        /* ignore */
      }
    }
  }

  async function judge(match: boolean) {
    if (!reveal.value) return
    reveal.value.verdict = match ? 'match' : 'miss'
    await api.post(`/rounds/${reveal.value.roundId}/verdict`, { match }).catch(() => {})
  }

  /** "Let it go": the answers dissolve on this phone. Nothing was kept on the server anyway. */
  function letGo() {
    reveal.value = null
  }

  function endTonight(): number {
    const n = tonight.value
    tonight.value = 0
    try {
      sessionStorage.removeItem(TONIGHT_KEY)
    } catch {
      /* ignore */
    }
    return n
  }

  async function tug() {
    try {
      await api.post('/rounds/tug')
      toast(`Tug sent to ${auth.partnerName}.`)
    } catch (e) {
      toast(e instanceof ApiError && e.code === 'slow_down' ? 'Give them a moment.' : 'Couldn’t send that.')
    }
  }

  // ── From the other phone ──

  async function onEvent(msg: { type: string; [k: string]: unknown }) {
    const by = msg.by as string | undefined
    switch (msg.type) {
      case 'round.drawn':
        home.clearReady()
        // Fetch the new card *before* clearing the old screen. Clearing first left a moment with
        // nothing on the table, and the Play screen took that as "go home".
        await loadCurrent()
        clearOutcome()
        break
      case 'round.empty':
        home.clearReady()
        clearOutcome()
        empty.value = true
        break
      case 'round.reshuffled':
        if (by !== myId()) {
          toBetween()
          home.say(`${auth.partnerName} shuffled them back in`)
        }
        break
      case 'round.sealed':
        await loadCurrent()
        break
      case 'round.hold':
        partnerHolding.value = !!msg.holding
        break
      case 'round.pull':
        partnerPulled.value = true
        partnerReadAlone.value = !!msg.read
        break
      case 'round.revealed': {
        const out = msg as unknown as PullOut & { round_id: string }
        // Already read on this phone (you read it alone earlier, and they've now pulled theirs):
        // just make sure it isn't still sitting here half-pulled.
        if (readHere.has(out.round_id)) {
          if (round.value?.id === out.round_id) accept(null)
          break
        }
        await showReveal(out.round_id, out, round.value)
        break
      }
      case 'round.passed':
        if (msg.turn_user_id) home.turnUserId = msg.turn_user_id as string
        accept(null)
        if (by !== myId()) passedBy.value = by ?? 'them'
        break
      case 'round.verdict':
        if (reveal.value && reveal.value.roundId === msg.round_id && by !== myId())
          reveal.value.verdict = msg.match ? 'match' : 'miss'
        break
      case 'round.expired':
        if (round.value?.id === msg.round_id) {
          accept(null)
          expired.value = true
        }
        break
      case 'tug':
        toast(`${auth.partnerName} gave the rope a little tug.`)
        break
    }
  }

  function reset() {
    accept(null)
    clearOutcome()
    loaded.value = false
  }

  return {
    round,
    loaded,
    reveal,
    passedBy,
    empty,
    expired,
    between,
    busy,
    draft,
    choice,
    partnerHolding,
    partnerPulled,
    partnerReadAlone,
    iPulled,
    tonight,
    phase,
    leaving,
    loadCurrent,
    draw,
    reshuffle,
    ready,
    seal,
    pass,
    hold,
    pull,
    judge,
    letGo,
    endTonight,
    tug,
    onEvent,
    clearOutcome,
    toBetween,
    reset,
  }
})
