<script setup lang="ts">
/**
 * The game, as one screen that moves through:
 *   answer → waiting (sealed, then hold to pull) → reveal → let it go → next
 * plus the side paths: they passed, the hat is empty, it expired.
 *
 * Gestures: swipe up on the revealed answers to let them go; swipe left afterwards to draw
 * the next one. The ≡ button opens Settings at any point; the round waits on the server.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Menu, X } from 'lucide-vue-next'
import HoldKnot from '@/components/HoldKnot.vue'
import KnotTie from '@/components/KnotTie.vue'
import PassSheet from '@/components/PassSheet.vue'
import { useSwipe } from '@/lib/swipe'
import { categoryDot, personTint } from '@/lib/theme'
import { toast } from '@/lib/toast'
import { fillName } from '@/lib/words'
import { useAuth } from '@/stores/auth'
import { CATEGORIES, DEPTHS, useHome } from '@/stores/home'
import { useRound } from '@/stores/round'
import { useTheme } from '@/stores/theme'

const auth = useAuth()
const home = useHome()
const game = useRound()
const theme = useTheme()
const router = useRouter()

const myId = computed(() => auth.me?.id ?? '')
const myName = computed(() => auth.me?.display_name ?? 'You')
const P = computed(() => auth.me?.partner?.display_name ?? 'Them')
const mine = computed(() => personTint(theme.prefs.accentHue, theme.prefs.mode))
const theirs = computed(() => personTint(auth.me?.partner?.theme?.accent_hue ?? 190, theme.prefs.mode))

onMounted(async () => {
  if (!game.loaded) await game.loadCurrent()
  if (game.phase === 'none') router.replace({ name: 'home' })
})

// ── The question on the table (live round, or the one just revealed) ──
const q = computed(() => game.round?.question ?? game.reveal?.question ?? null)
const subjectId = computed(() => game.round?.subject_id ?? game.reveal?.subjectId ?? null)
const iAmSubject = computed(() => subjectId.value === myId.value)
const qText = computed(() => {
  if (!q.value) return ''
  return fillName(q.value.text, iAmSubject.value ? myName.value : P.value)
})
const catLine = computed(() => {
  if (!q.value) return ''
  const c = CATEGORIES.find((x) => x.id === q.value!.category)?.label ?? ''
  const d = DEPTHS.find((x) => x.id === q.value!.depth)?.label ?? ''
  return `${c} · ${d}`
})
// Next card: both here → "ready" handshake; they're away → you draw and leave it sealed.
const away = computed(() => !home.partnerOnline)
const nextLabel = computed(() => {
  if (away.value) return `Leave another for ${P.value}`
  if (home.readyMe) return `Waiting for ${P.value}… (tap to undo)`
  return home.readyThem ? `${P.value} is ready. You too?` : 'Ready for the next one'
})

// ── Answering ──
const showPass = ref(false)
const answered = computed(() =>
  q.value?.type === 'wyr' ? game.choice !== null : game.draft.trim().length > 0,
)
const leaving = computed(() => game.leaving)

async function seal() {
  if (!answered.value) return toast(q.value?.type === 'wyr' ? 'Pick a side first.' : 'Write a little something first.')
  try {
    await game.seal()
  } catch {
    return
  }
  if (leaving.value && !game.round?.partner_sealed) {
    toast('Sealed and left. It keeps for 24 hours.')
    router.replace({ name: 'home' })
  }
}
async function doPass(retire: boolean) {
  showPass.value = false
  await game.pass(retire)
  toast(retire ? 'Gone for good.' : 'Passed.')
  router.replace({ name: 'home' })
}

// ── Waiting ──
const ready = computed(() => game.round?.state === 'ready')
const iWrite = computed(() => !!game.round?.i_answer)
const waitTitle = computed(() => {
  const r = game.round
  if (!r) return ''
  if (ready.value) {
    if (q.value?.type === 'self') return iWrite.value ? `${P.value} is ready to read.` : `${P.value} wrote it.`
    return `${P.value} sealed theirs too.`
  }
  if (!iWrite.value) return `${P.value} is writing`
  return `Sealed. Waiting for ${P.value}`
})
const waitSub = computed(() => {
  if (!ready.value) {
    if (!iWrite.value) return 'You’ll read it when they’re done.'
    return 'Your answer is knotted up tight. Nobody can peek, not even us.'
  }
  if (!home.partnerOnline && !game.partnerPulled)
    return game.iPulled
      ? `${P.value} left before pulling. Read it now; they’ll pull theirs when they’re back.`
      : `${P.value} isn’t here right now. Pull your end to read it; they’ll see it when they’re back.`
  if (game.partnerReadAlone && !game.iPulled) return `${P.value} already read it. Pull your end whenever you’re ready.`
  if (game.iPulled && !game.partnerPulled) return `Hold on, ${P.value} is pulling too.`
  if (game.partnerPulled && !game.iPulled) return `${P.value} is holding their end. Press and hold yours.`
  if (game.partnerHolding) return `${P.value} is reaching for the rope…`
  return 'Press and hold the knot together.'
})
// If you've pulled and they haven't for a while, offer to read it now.
const offerAlone = ref(false)
let aloneTimer: ReturnType<typeof setTimeout> | undefined
watch(
  () => game.iPulled && !game.partnerPulled,
  (waitingOnThem) => {
    clearTimeout(aloneTimer)
    offerAlone.value = false
    if (waitingOnThem) aloneTimer = setTimeout(() => (offerAlone.value = true), 15000)
  },
  { immediate: true }, // also when you come back to a card you'd already pulled
)
onBeforeUnmount(() => clearTimeout(aloneTimer))

// ── Reveal ──
type Body = { t?: string; c?: 0 | 1 } | null
const show = (b: Body) => {
  if (!b) return '…'
  if (q.value?.type === 'wyr' && b.c !== undefined) return q.value.options?.[b.c] ?? '…'
  return b.t ?? '…'
}
const rv = computed(() => game.reveal)
const myText = computed(() => show(rv.value?.mine ?? null))
const theirText = computed(() => show(rv.value?.theirs ?? null))
const labels = computed(() => {
  if (q.value?.type === 'guess')
    return iAmSubject.value
      ? { mine: 'The truth', theirs: `${P.value} guessed` }
      : { mine: 'Your guess', theirs: `${P.value}, truthfully` }
  return { mine: 'You', theirs: P.value }
})
const writerIsMe = computed(() => rv.value?.drawnBy === myId.value)
const selfText = computed(() => (writerIsMe.value ? myText.value : theirText.value))
const writerName = computed(() => (writerIsMe.value ? myName.value : P.value))

const outcome = computed(() => {
  const r = rv.value
  if (!r || !q.value) return null
  const t = q.value.type
  if (t === 'guess') {
    if (r.verdict === 'match')
      return {
        win: true,
        title: r.auto ? 'Nailed it.' : iAmSubject.value ? 'You let it slide.' : `${P.value} let it slide.`,
        sub: iAmSubject.value ? `${P.value} knows you a little too well.` : `You know ${P.value} a little too well.`,
      }
    if (r.verdict === 'miss')
      return {
        miss: true,
        title: 'Ha. Not even close.',
        sub: iAmSubject.value ? `${P.value} owes you a better guess.` : `${P.value} will bring this up for weeks.`,
      }
    return iAmSubject.value ? { judge: true } : { awaiting: true }
  }
  if (t === 'wyr') {
    const same = r.mine?.c !== undefined && r.mine?.c === r.theirs?.c
    return same
      ? { win: true, title: 'Same side of the rope.', sub: 'Of course you did.' }
      : { miss: true, title: 'Tug of war.', sub: 'Settle it out loud.' }
  }
  if (t === 'both') return { title: 'Now say more about that.', sub: 'Out loud this time.' }
  return null
})

const SPARKS = Array.from({ length: 18 }, (_, i) => {
  const a = (i / 18) * Math.PI * 2
  const r = 70 + (i % 3) * 28
  return {
    width: i % 2 ? '5px' : '7px',
    height: i % 2 ? '5px' : '7px',
    background: i % 3 ? 'var(--accent)' : 'var(--ink)',
    '--dx': `${Math.round(Math.cos(a) * r)}px`,
    '--dy': `${Math.round(Math.sin(a) * r)}px`,
    animationDelay: `${1.5 + (i % 4) * 0.05}s`,
  }
})

// ── Next card, straight from the reveal ──
// No in-between screen after a reveal: the answers stay up until the next card is dealt.
// ("between" is only the shared "ready when you both are" moment after a pass, expiry or reshuffle.)
async function next() {
  if (away.value) {
    game.letGo()
    await game.draw()
    return
  }
  await game.ready(!home.readyMe)
}
async function shuffleAndDraw() {
  await game.reshuffle() // both here: also counts as "ready", so one tap from them deals
  if (away.value) await game.draw()
}
function enough() {
  if (home.readyMe) game.ready(false)
  game.clearOutcome()
  router.replace({ name: 'tonight' })
}
// Nothing on the table and nothing to show (e.g. they passed and you went back): go home.
watch(
  () => [game.phase, game.busy] as const,
  ([phase, busy]) => {
    if (phase === 'none' && !busy && game.loaded) router.replace({ name: 'home' })
  },
)

// ── Where the other person is (so nobody waits at the table alone without knowing) ──
const notice = computed(() => {
  if (home.activity) return home.activity // e.g. "Ama changed depth to Deep"
  if (!home.partnerOnline) return `${P.value} is away. Anything you seal waits for them.`
  const w = home.partnerWhere
  if (w === 'home') return `${P.value} went back to the home screen.`
  if (w === 'settings') return `${P.value} is in Settings.`
  if (w === 'unlock') return `${P.value} is re-entering the phrase.`
  return ''
})

// ── Gestures ──
const revealEl = ref<HTMLElement | null>(null)
const betweenEl = ref<HTMLElement | null>(null)
useSwipe(revealEl, { left: next })
useSwipe(betweenEl, { left: next })

function close() {
  router.replace({ name: 'home' })
}
</script>

<template>
  <main class="play">
    <!-- Header: close · settings · what this card is · pass -->
    <header class="bar">
      <div class="left">
        <button class="round-btn" type="button" aria-label="Close" @click="close"><X :size="20" :stroke-width="1.6" /></button>
        <button class="round-btn" type="button" aria-label="Settings" @click="router.push({ name: 'settings' })">
          <Menu :size="18" :stroke-width="1.6" />
        </button>
      </div>
      <div v-if="q && game.phase !== 'none'" class="cat">
        <span class="dot" :style="{ background: categoryDot(q.category) }" />{{ catLine }}
      </div>
      <button v-if="game.phase === 'answer'" class="pass" type="button" @click="showPass = true">Pass</button>
      <span v-else class="spacer" />
    </header>
    <Transition name="notice">
      <p v-if="notice && game.phase !== 'answer'" :key="notice" class="notice" role="status">{{ notice }}</p>
    </Transition>

    <!-- ── Answering ── -->
    <section v-if="game.phase === 'answer' && q" class="answer">
      <p v-if="leaving" class="leave-note">For {{ P }} to find later · keeps 24 hours</p>

      <div class="cardwrap" :key="game.round?.id">
        <!-- Guess (about them) / About you -->
        <template v-if="q.type === 'guess'">
          <div class="qcard guess" :class="{ me: iAmSubject }">
            <span class="watermark">{{ iAmSubject ? '!' : '?' }}</span>
            <div class="qmeta">
              <span>{{ iAmSubject ? 'About you' : 'Guess' }}</span>
              <span class="muted">{{ iAmSubject ? `${P} is guessing` : `about ${P}` }}</span>
            </div>
            <p class="qtext">{{ qText }}</p>
          </div>
          <textarea
            v-model="game.draft"
            class="answer-box"
            :placeholder="iAmSubject ? 'The honest truth…' : 'Your best guess…'"
            enterkeyhint="done"
            maxlength="1500"
          />
          <p class="hint">
            {{ iAmSubject ? 'At the reveal, you get to say if they were close enough.' : `${P} writes the truth and decides how close you got.` }}
          </p>
        </template>

        <!-- Both answer -->
        <template v-else-if="q.type === 'both'">
          <div class="qcard both">
            <div class="qmeta">
              <span>You both answer</span><span class="muted">{{ myName }} + {{ P }}</span>
            </div>
            <p class="qtext">{{ qText }}</p>
          </div>
          <textarea v-model="game.draft" class="answer-box tall" placeholder="Say it how you'd say it…" maxlength="1500" />
        </template>

        <!-- Would you rather -->
        <template v-else-if="q.type === 'wyr'">
          <div class="wyr-head">
            <span class="eyebrow">Would you rather</span>
            <p class="qtext wyr">{{ qText }}</p>
          </div>
          <button class="opt" :class="{ on: game.choice === 0 }" type="button" @click="game.choice = 0">
            <span class="letter">A</span><span>{{ q.options?.[0] }}</span>
          </button>
          <div class="or"><span />or<span /></div>
          <button class="opt" :class="{ on: game.choice === 1 }" type="button" @click="game.choice = 1">
            <span class="letter">B</span><span>{{ q.options?.[1] }}</span>
          </button>
        </template>

        <!-- Just you -->
        <template v-else>
          <div class="selfcard">
            <span class="label">Just you · {{ P }} will read it</span>
            <p class="selftext">{{ qText }}</p>
          </div>
          <textarea v-model="game.draft" class="answer-box self" placeholder="Take your time…" maxlength="3000" />
          <p class="hint">There's no wrong length. Or you can pass.</p>
        </template>
      </div>

      <button class="btn seal" type="button" :class="{ dim: !answered }" :disabled="game.busy" @click="seal">
        {{ game.busy ? 'Sealing…' : leaving ? `Seal it for ${P}` : 'Seal my answer' }}
      </button>
    </section>

    <!-- ── Waiting / hold to pull ── -->
    <section v-else-if="game.phase === 'waiting' && q" class="waiting">
      <p class="small-q">{{ qText }}</p>
      <div class="wait-mid">
        <h2 class="wait-title">
          <span v-if="ready" class="pop">{{ waitTitle }}</span>
          <span v-else>{{ waitTitle }}<span class="d">.</span><span class="d d2">.</span><span class="d d3">.</span></span>
        </h2>
        <HoldKnot
          :ready="ready"
          :mine="mine.ring"
          :theirs="theirs.ring"
          :partner-holding="game.partnerHolding"
          :partner-pulled="game.partnerPulled"
          :i-pulled="game.iPulled"
          @holding="game.hold"
          @pulled="game.pull()"
        />
        <div class="legend">
          <span><i :style="{ background: mine.ring }" />You</span>
          <span><i :style="{ background: theirs.ring }" />{{ P }}</span>
        </div>
        <p class="wait-sub">{{ waitSub }}</p>
      </div>
      <template v-if="!ready">
        <button class="btn ghost" type="button" @click="game.tug()">Give {{ P }} a little tug</button>
        <button v-if="away && iWrite" class="btn link" type="button" :disabled="game.busy" @click="game.draw()">
          Leave {{ P }} another one
        </button>
      </template>
      <button v-else-if="!game.iPulled" class="btn ghost" type="button" @click="game.pull()">
        Can't hold? Tap to pull your end
      </button>
      <button v-else-if="offerAlone || away" class="btn" type="button" @click="game.pull(true)">
        Read it now. {{ P }} still gets to pull theirs.
      </button>
    </section>

    <!-- ── Reveal ── -->
    <section v-else-if="game.phase === 'reveal' && rv && q" ref="revealEl" class="reveal">
      <p class="small-q">{{ qText }}</p>

      <div v-if="q.type !== 'self'" class="pair">
        <svg class="rope" width="40" height="420" viewBox="0 0 40 420" fill="none" aria-hidden="true">
          <path d="M20,0 C2,70 38,140 20,210 S2,350 20,420" pathLength="100" />
        </svg>
        <div class="slot down">
          <div class="acard" :style="{ background: mine.bg, boxShadow: `inset 0 0 0 1.5px ${mine.ring}, 0 20px 40px -24px var(--glow)` }">
            <span class="alabel" :style="{ color: mine.ink }">{{ labels.mine }}</span>
            <p class="atext">{{ myText }}</p>
          </div>
        </div>
        <div class="untie">
          <KnotTie :w="90" mode="untie" :stroke-width="11" />
          <template v-if="outcome && 'win' in outcome && outcome.win">
            <span v-for="(s, i) in SPARKS" :key="i" class="spark" :style="s" />
          </template>
        </div>
        <div class="slot up">
          <div class="acard" :style="{ background: theirs.bg, boxShadow: `inset 0 0 0 1.5px ${theirs.ring}, 0 20px 40px -24px var(--glow)` }">
            <span class="alabel" :style="{ color: theirs.ink }">{{ labels.theirs }}</span>
            <p class="atext">{{ theirText }}</p>
          </div>
        </div>
      </div>

      <div v-else class="selfreveal">
        <KnotTie :w="90" mode="untie" :stroke-width="10" />
        <div class="selfcard-out" :style="{ background: `radial-gradient(ellipse at 50% 0%, color-mix(in oklch, ${(writerIsMe ? mine : theirs).ring} 30%, transparent), transparent 75%)` }">
          <span class="label">{{ writerName }}, in their own words</span>
          <p class="selftext">{{ selfText }}</p>
        </div>
        <p v-if="writerIsMe" class="read-twice">{{ P }} read it twice. ♡</p>
      </div>

      <div class="verdict">
        <template v-if="outcome && 'judge' in outcome">
          <p class="judge-q">Close enough? Your call.</p>
          <div class="judge">
            <button class="btn small" type="button" @click="game.judge(true)">Basically, yes</button>
            <button class="btn ghost small" type="button" @click="game.judge(false)">Not even close</button>
          </div>
        </template>
        <p v-else-if="outcome && 'awaiting' in outcome" class="await">
          Waiting for {{ P }}'s verdict<span class="d">.</span><span class="d d2">.</span><span class="d d3">.</span>
        </p>
        <template v-else-if="outcome && 'title' in outcome">
          <p class="v-title" :class="{ miss: 'miss' in outcome }">{{ outcome.title }}</p>
          <p class="v-sub">{{ outcome.sub }}</p>
        </template>
      </div>

      <div class="reveal-actions">
        <button class="btn" :class="{ armed: home.readyMe && !away }" type="button" :disabled="game.busy" @click="next">
          {{ nextLabel }}
        </button>
        <button class="btn ghost" type="button" @click="enough">That's enough for tonight</button>
        <p class="gesture">or swipe left for the next one</p>
      </div>
    </section>

    <!-- ── Between cards after a pass / expiry / reshuffle: ready together ── -->
    <section v-else-if="game.phase === 'between'" ref="betweenEl" class="after">
      <div class="after-mid">
        <KnotTie :w="110" mode="tie" :delay="0.2" glow />
        <p class="after-title">Ready when you both are.</p>
      </div>
      <div class="after-actions">
        <button class="btn" :class="{ armed: home.readyMe && !away }" type="button" :disabled="game.busy" @click="next">
          {{ nextLabel }}
        </button>
        <button class="btn ghost" type="button" @click="enough">That's enough for tonight</button>
        <p class="gesture">or swipe left</p>
      </div>
    </section>

    <!-- ── They passed ── -->
    <section v-else-if="game.phase === 'passed'" class="center-state">
      <div class="mid">
        <svg class="sway" width="180" height="70" viewBox="0 0 180 70" fill="none" aria-hidden="true">
          <path d="M6,14 Q90,96 174,14" pathLength="100" class="slack" />
        </svg>
        <h2 class="state-title">{{ P }} passed on that one.</h2>
        <p class="state-sub">No reason needed. Your answer was let go, unread.</p>
      </div>
      <div class="stack">
        <button class="btn" :class="{ armed: home.readyMe && !away }" type="button" @click="(game.toBetween(), next())">
          {{ nextLabel }}
        </button>
        <button class="btn ghost" type="button" @click="(game.clearOutcome(), close())">Back home</button>
      </div>
    </section>

    <!-- ── Hat is empty ── -->
    <section v-else-if="game.phase === 'empty'" class="center-state">
      <div class="mid">
        <div class="empty-deck" aria-hidden="true"><span /><span /><span>∅</span></div>
        <h2 class="state-title">You've drawn every card in this mix.</h2>
        <p class="state-sub">Try another depth or add a category, and the hat fills right back up.</p>
      </div>
      <div class="stack">
        <button class="btn" type="button" @click="(game.clearOutcome(), close())">Change the mix</button>
        <button class="btn ghost" type="button" @click="shuffleAndDraw">Shuffle them back in</button>
        <p v-if="!away" class="gesture">Then tap ready together.</p>
      </div>
    </section>

    <!-- ── Expired ── -->
    <section v-else-if="game.phase === 'expired'" class="center-state">
      <div class="mid">
        <KnotTie :w="180" mode="untie" :delay="0.6" />
        <h2 class="state-title">That one came undone.</h2>
        <p class="state-sub">It sat sealed for 24 hours, so we let it go. Nobody opened it.</p>
      </div>
      <div class="stack">
        <button class="btn" :class="{ armed: home.readyMe && !away }" type="button" @click="(game.toBetween(), next())">
          {{ nextLabel }}
        </button>
        <button class="btn ghost" type="button" @click="(game.clearOutcome(), close())">Back home</button>
      </div>
    </section>

    <PassSheet v-if="showPass" :partner="P" @pass="doPass(false)" @retire="doPass(true)" @close="showPass = false" />
  </main>
</template>

<style scoped>
.play {
  height: 100dvh;
  max-width: 480px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: max(58px, calc(var(--safe-top) + 10px)) 22px max(40px, calc(var(--safe-bottom) + 8px));
  overflow: hidden;
}
.play > section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* Header */
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex: none;
}
.left {
  display: flex;
  gap: 8px;
}
.round-btn {
  width: 44px;
  height: 44px;
  border-radius: 22px;
  border: 1px solid var(--line);
  background: none;
  display: grid;
  place-items: center;
  padding: 0;
}
.cat {
  display: flex;
  align-items: center;
  gap: 8px;
  font: 600 13px/1 var(--sans);
  color: var(--muted);
  white-space: nowrap;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.pass {
  height: 44px;
  padding: 0 16px;
  border-radius: 22px;
  border: 1px solid var(--line);
  background: none;
  font: 600 14px/1 var(--sans);
}
.spacer {
  width: 44px;
}
.notice {
  margin: -4px 0 0;
  align-self: center;
  max-width: 100%;
  padding: 8px 14px;
  border-radius: 14px;
  background: var(--surface);
  font: 500 13px/1.3 var(--sans);
  text-align: center;
  flex: none;
}
.notice-enter-active,
.notice-leave-active {
  transition: opacity 0.3s, transform 0.3s;
}
.notice-enter-from,
.notice-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* Answering */
.answer {
  gap: 16px;
}
.leave-note {
  margin: 0;
  text-align: center;
  font: 500 12px/1.3 var(--sans);
  color: var(--accentInk);
}
.cardwrap {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  animation: cardIn calc(0.8s * var(--m)) cubic-bezier(0.2, 0.8, 0.2, 1) both;
  scrollbar-width: none;
}
.qcard {
  position: relative;
  overflow: hidden;
  border-radius: 28px;
  padding: 26px 24px 30px;
  background: var(--surface);
  display: flex;
  flex-direction: column;
  gap: 18px;
  flex: none;
}
.qcard.guess {
  border: 1.5px dashed var(--accent2);
}
.qcard.guess.me {
  border-style: solid;
}
.qcard.both {
  box-shadow: inset 0 2px 0 var(--accent);
}
.watermark {
  position: absolute;
  right: -6px;
  top: -34px;
  font: italic 500 210px/1 var(--serif);
  color: var(--accent);
  opacity: 0.08;
  pointer-events: none;
}
.qmeta {
  display: flex;
  justify-content: space-between;
  font: 700 11px/1 var(--sans);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--accentInk);
}
.muted {
  color: var(--muted);
}
.qtext {
  margin: 0;
  font: 500 31px/1.12 var(--serif);
  text-wrap: pretty;
}
.qtext.wyr {
  font-size: 29px;
}
.answer-box {
  min-height: 110px;
  width: 100%;
  border-radius: 20px;
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink);
  padding: 16px 18px;
  font: 400 16px/1.45 var(--sans);
  resize: none;
  outline: none;
  flex: none;
}
.answer-box:focus {
  border-color: var(--accent);
}
.answer-box.tall {
  min-height: 120px;
}
.answer-box.self {
  min-height: 130px;
  border: none;
  border-bottom: 1px solid var(--line);
  border-radius: 0;
  background: transparent;
  padding: 8px 4px;
  font: italic 400 21px/1.45 var(--serif);
  text-align: center;
}
.hint {
  margin: 0;
  font: 400 13px/1.45 var(--sans);
  color: var(--muted);
  text-align: center;
}
.wyr-head {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 6px 4px 4px;
}
.opt {
  min-height: 84px;
  width: 100%;
  border-radius: 24px;
  border: 1px solid var(--line);
  background: var(--surface);
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 22px;
  font: 500 24px/1.15 var(--serif);
  text-align: left;
  transition: all 0.25s cubic-bezier(0.3, 1.4, 0.5, 1);
  flex: none;
}
.opt.on {
  border: 2px solid var(--accent);
  background: var(--accent);
  color: var(--onAccent);
  transform: scale(1.02);
  box-shadow: 0 14px 30px -14px var(--glow);
}
.letter {
  font: 700 11px/1 var(--sans);
  letter-spacing: 0.16em;
  opacity: 0.7;
}
.or {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--muted);
  font: italic 500 20px/1 var(--serif);
}
.or span {
  flex: 1;
  height: 1px;
  background: var(--line);
}
.selfcard {
  border-radius: 28px;
  padding: 34px 24px 38px;
  background: radial-gradient(ellipse at 50% 0%, var(--glow), transparent 72%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  text-align: center;
  flex: none;
}
.label {
  font: 700 11px/1 var(--sans);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted);
}
.selftext {
  margin: 0;
  font: italic 400 30px/1.25 var(--serif);
  text-wrap: balance;
  opacity: 0.92;
}
.seal {
  flex: none;
}
.seal.dim {
  opacity: 0.45;
}

/* Waiting */
.waiting {
  align-items: center;
  gap: 16px;
}
.small-q {
  margin: 0;
  font: italic 400 20px/1.3 var(--serif);
  color: var(--muted);
  text-align: center;
  max-width: 310px;
  text-wrap: balance;
}
.wait-mid {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
}
.wait-title {
  margin: 0;
  font: 500 30px/1.1 var(--serif);
  text-align: center;
  min-height: 66px;
  text-wrap: balance;
}
.pop {
  display: inline-block;
  animation: popIn 0.5s ease both;
}
.d {
  animation: dots 1.4s infinite;
}
.d2 {
  animation-delay: 0.2s;
}
.d3 {
  animation-delay: 0.4s;
}
.legend {
  display: flex;
  gap: 28px;
  font: 600 12px/1 var(--sans);
  color: var(--muted);
}
.legend span {
  display: flex;
  align-items: center;
  gap: 6px;
}
.legend i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.wait-sub {
  margin: 0;
  font: 500 14px/1.45 var(--sans);
  text-align: center;
  max-width: 280px;
  min-height: 40px;
  text-wrap: pretty;
}

/* Reveal */
.reveal {
  align-items: center;
  gap: 12px;
}
.pair {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: none;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
}
.rope {
  position: absolute;
  left: 50%;
  top: 50%;
  margin: -210px 0 0 -20px;
  pointer-events: none;
}
.rope path {
  stroke: var(--accent2);
  stroke-width: 5;
  stroke-linecap: round;
  stroke-dasharray: 100;
  animation: ropeDraw calc(1.1s * var(--m)) calc(0.6s * var(--m)) ease both;
}
.slot {
  position: relative;
  width: 100%;
}
.slot.down {
  animation: outDown calc(1s * var(--m)) calc(0.75s * var(--m)) cubic-bezier(0.2, 0.9, 0.25, 1.1) both;
}
.slot.up {
  animation: outUp calc(1s * var(--m)) calc(0.75s * var(--m)) cubic-bezier(0.2, 0.9, 0.25, 1.1) both;
}
.acard {
  border-radius: 24px;
  padding: 18px 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.alabel {
  font: 700 11px/1 var(--sans);
  letter-spacing: 0.16em;
  text-transform: uppercase;
}
.atext {
  margin: 0;
  font: 500 25px/1.2 var(--serif);
  text-wrap: pretty;
  overflow-wrap: anywhere;
}
.untie {
  position: relative;
  width: 90px;
  height: 54px;
  flex: none;
}
.spark {
  position: absolute;
  left: 42px;
  top: 24px;
  border-radius: 50%;
  animation: spark 1.1s ease-out both;
}
.selfreveal {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 24px;
}
.selfcard-out {
  width: 100%;
  padding: 30px 24px;
  border-radius: 28px;
  text-align: center;
  animation: outUp calc(1.3s * var(--m)) calc(0.6s * var(--m)) ease both;
}
.selfcard-out .label {
  display: block;
  margin-bottom: 16px;
}
.read-twice {
  margin: 0;
  font: 500 14px/1.5 var(--sans);
  color: var(--muted);
  animation: fadeIn 1s 2s ease both;
}
.verdict {
  min-height: 72px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  text-align: center;
}
.judge-q {
  margin: 0;
  font: 500 22px/1.1 var(--serif);
  animation: fadeIn 0.5s 1.5s ease both;
}
.judge {
  display: flex;
  gap: 10px;
  animation: fadeIn 0.5s 1.7s ease both;
}
.btn.small {
  height: 44px;
  width: auto;
  padding: 0 20px;
  font-size: 14px;
}
.await {
  margin: 0;
  font: italic 400 20px/1.2 var(--serif);
  color: var(--muted);
  animation: fadeIn 0.5s 1.5s ease both;
}
.v-title {
  margin: 0;
  font: 500 30px/1.1 var(--serif);
  color: var(--accentInk);
  animation: popIn 0.6s 1.5s ease both;
}
.v-title.miss {
  animation:
    popIn 0.5s 1.5s ease both,
    wobble 0.6s 2s ease;
}
.v-sub {
  margin: 0;
  font: 400 13px/1.4 var(--sans);
  color: var(--muted);
  animation: fadeIn 0.5s 1.8s ease both;
}
.reveal-actions {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
  animation: fadeIn 0.6s 1.6s ease both;
}
.gesture {
  margin: -6px 0 0;
  text-align: center;
  font: 400 12px/1 var(--sans);
  color: var(--muted);
  opacity: 0.7;
}

/* After letting go */
.after {
  position: relative;
  align-items: center;
  gap: 18px;
}
.dissolving {
  position: absolute;
  top: 18%;
  left: 0;
  right: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  pointer-events: none;
}
.gone {
  margin: 0;
  font: 500 24px/1.2 var(--serif);
  text-align: center;
  animation: dissolve calc(2.2s * var(--m)) 0.2s ease-in both;
}
.gone.later {
  animation-delay: 0.5s;
}
.after-mid {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  text-align: center;
  animation: fadeIn calc(1.2s * var(--m)) calc(1.6s * var(--m)) ease both;
}
.after-title {
  margin: 0;
  font: 400 14px/1.5 var(--sans);
  color: var(--muted);
}
.btn.armed {
  background: transparent;
  color: var(--ink);
  border: 1.5px dashed var(--accent);
  box-shadow: none;
}
.after-actions {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
  animation: fadeIn 0.8s calc(2.2s * var(--m)) ease both;
}

/* Centered states */
.center-state {
  gap: 22px;
}
.mid {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 24px;
  text-align: center;
}
.state-title {
  margin: 0;
  font: 500 34px/1.05 var(--serif);
  text-wrap: balance;
}
.state-sub {
  margin: 0;
  font: 400 15px/1.5 var(--sans);
  color: var(--muted);
  max-width: 290px;
  text-wrap: pretty;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.sway {
  transform-origin: 50% 0;
  animation: sway 3s ease-in-out infinite;
}
.slack {
  stroke: var(--accent2);
  stroke-width: 7;
  stroke-linecap: round;
  stroke-dasharray: 100;
  animation: ropeDraw 1.2s ease both;
}
.empty-deck {
  position: relative;
  width: 150px;
  height: 150px;
}
.empty-deck span {
  position: absolute;
  top: 10px;
  width: 96px;
  height: 128px;
  border-radius: 14px;
  border: 1.5px dashed var(--line);
}
.empty-deck span:nth-child(1) {
  left: 20px;
  transform: rotate(-8deg);
}
.empty-deck span:nth-child(2) {
  left: 34px;
  transform: rotate(7deg);
}
.empty-deck span:nth-child(3) {
  left: 27px;
  top: 12px;
  border-color: var(--accent2);
  display: grid;
  place-items: center;
  font: italic 500 40px/1 var(--serif);
  color: var(--muted);
  animation: breathe 3s ease-in-out infinite;
}

@keyframes cardIn {
  from { opacity: 0; transform: perspective(900px) rotateY(75deg) translateY(30px); }
  to { opacity: 1; transform: none; }
}
@keyframes outUp {
  0% { opacity: 0; transform: translateY(110px) scale(0.35); }
  55% { opacity: 1; }
  100% { opacity: 1; transform: none; }
}
@keyframes outDown {
  0% { opacity: 0; transform: translateY(-110px) scale(0.35); }
  55% { opacity: 1; }
  100% { opacity: 1; transform: none; }
}
@keyframes popIn {
  0% { opacity: 0; transform: scale(0.6); }
  70% { opacity: 1; transform: scale(1.08); }
  100% { opacity: 1; transform: none; }
}
@keyframes spark {
  0% { transform: translate(0, 0) scale(1); opacity: 1; }
  100% { transform: translate(var(--dx), var(--dy)) scale(0.2); opacity: 0; }
}
@keyframes wobble {
  0%, 100% { transform: rotate(0); }
  20% { transform: rotate(-5deg); }
  40% { transform: rotate(4deg); }
  60% { transform: rotate(-3deg); }
  80% { transform: rotate(2deg); }
}
@keyframes dissolve {
  0% { opacity: 1; filter: blur(0); transform: none; }
  100% { opacity: 0; filter: blur(12px); transform: translateY(-40px) scale(1.06); }
}
@keyframes dots {
  0%, 20% { opacity: 0.2; }
  50% { opacity: 1; }
  100% { opacity: 0.2; }
}
@keyframes sway {
  0%, 100% { transform: rotate(-4deg); }
  50% { transform: rotate(4deg); }
}
@keyframes breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}
@keyframes ropeDraw {
  from { stroke-dashoffset: 100; }
  to { stroke-dashoffset: 0; }
}
</style>
