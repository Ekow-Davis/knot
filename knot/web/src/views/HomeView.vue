<script setup lang="ts">
/**
 * Home: who's here, whose turn it is, the deck, how deep tonight, and what's in the hat.
 * Depth and the hat are shared: a change on either phone shows on both.
 * (Drawing a question arrives in Session 5.)
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronDown } from 'lucide-vue-next'
import KnotTie from '@/components/KnotTie.vue'
import { useSwipe } from '@/lib/swipe'
import { categoryDot, personTint } from '@/lib/theme'
import { useAuth } from '@/stores/auth'
import { CATEGORIES, DEPTHS, useHome } from '@/stores/home'
import { useRound } from '@/stores/round'
import { useTheme } from '@/stores/theme'

const auth = useAuth()
const home = useHome()
const theme = useTheme()
const router = useRouter()

const me = computed(() => auth.me)
const paired = computed(() => !!me.value?.pair_complete)
const P = computed(() => me.value?.partner?.display_name ?? 'Them')

const game = useRound()
onMounted(() => {
  if (paired.value && !home.loaded) home.load()
  if (paired.value) game.loadCurrent()
})

// ── Avatars: each person in the colour they picked ──
const myTint = computed(() => personTint(theme.prefs.accentHue, theme.prefs.mode))
const partnerTint = computed(() => personTint(me.value?.partner?.theme?.accent_hue ?? 38, theme.prefs.mode))
const initial = (name?: string | null) => (name?.trim()[0] ?? '·').toUpperCase()

const presence = computed(() => {
  if (!paired.value) return 'Waiting for your person to join'
  return home.activity || (home.partnerOnline ? `${P.value} is here, too` : `${P.value} is away right now`)
})

// ── Turn, or the card already on the table ──
const r = computed(() => game.round)
const away = computed(() => paired.value && !home.partnerOnline)
const canDraw = computed(() => home.myTurn || away.value)
const hoursLeft = computed(() => {
  if (!r.value) return ''
  const ms = new Date(r.value.expires_at).getTime() - Date.now()
  const h = Math.max(0, Math.floor(ms / 3_600_000))
  const m = Math.max(0, Math.floor((ms % 3_600_000) / 60_000))
  return `${h}h ${m}m`
})
const title = computed(() => {
  if (!paired.value) return 'Almost there.'
  const rnd = r.value
  if (rnd) {
    if (rnd.state === 'ready') return 'Both sealed. Pull it open together.'
    if (rnd.i_answer && !rnd.i_sealed)
      return rnd.drawn_by === me.value?.id ? 'Your card is waiting.' : `${P.value} drew one for you both.`
    return away.value ? `Left one for ${P.value}.` : `Waiting on ${P.value}.`
  }
  if (away.value) return `${P.value} isn’t around right now.`
  return home.myTurn ? 'Your turn to draw.' : `${P.value}’s turn to draw.`
})
const sub = computed(() => {
  if (!paired.value) return 'Make a pairing code in Settings and give it to the one person who should join you.'
  if (r.value) return 'It waits on the table until you’ve both answered. Nothing is kept after the reveal.'
  if (away.value) return 'Leave them a sealed question. It keeps for 24 hours.'
  if (home.settings.depth === 'deep') return 'Deep is slower and quieter. Only go here together.'
  return 'You both see these choices, and changes show up on both phones.'
})
const drawLabel = computed(() => {
  if (!paired.value) return 'Make a pairing code'
  if (r.value) return 'Open it'
  if (away.value) return 'Leave a sealed question'
  return home.myTurn ? 'Draw a question' : `Waiting on ${P.value}…`
})

// ── What the depths mean ──
const DEPTH_NOTES = [
  { id: 'light', label: 'Light', text: 'Easy and playful. Favourites, firsts, silly what-ifs. Good any time.' },
  {
    id: 'medium',
    label: 'Medium',
    text: 'More personal. Real preferences, feelings, the “why” behind things. For a quiet moment.',
  },
  {
    id: 'deep',
    label: 'Deep',
    text: 'The most intimate. Fears, hopes, desires, things you don’t usually say. Only go here together.',
  },
]

// ── Depth slider ──
const depthIndex = computed(() => DEPTHS.findIndex((d) => d.id === home.settings.depth))

// ── The hat ──
const chips = computed(() =>
  CATEGORIES.map((c) => {
    const s = home.settings
    let on: boolean
    let struck = false
    let note = ''
    let waiting = false
    if (c.id === 'spicy') {
      const st = home.spicyState
      on = st === 'both' || st === 'waiting'
      waiting = st === 'waiting'
      note = st === 'both' ? 'on for both' : st === 'waiting' ? `waiting on ${P.value}` : st === 'theirs' ? `${P.value} said yes` : ''
      struck = s.random && !on
    } else if (s.random) {
      struck = s.excluded.includes(c.id as never)
      on = !struck
    } else {
      on = s.categories.includes(c.id as never)
    }
    return { ...c, on, struck, note, waiting, dot: categoryDot(c.id) }
  }),
)

async function draw() {
  if (!paired.value) return router.push({ name: 'settings' })
  if (r.value) return router.push({ name: 'play' })
  if (!canDraw.value) return
  if (await game.draw()) router.push({ name: 'play' })
}

const deck = ref<HTMLElement | null>(null)
useSwipe(deck, { up: draw })
</script>

<template>
  <main v-if="me" class="home">
    <header class="top">
      <div class="brand">
        <KnotTie :w="40" mode="static" :stroke-width="13" />
        <span class="wordmark">Knot</span>
      </div>
      <button class="menu" type="button" aria-label="Settings" @click="router.push({ name: 'settings' })">
        <span /><span /><span />
      </button>
    </header>

    <div class="presence">
      <div class="pair-avatars">
        <span class="avatar" :style="{ color: myTint.ink, boxShadow: `inset 0 0 0 1.5px ${myTint.ring}` }">
          {{ initial(me.display_name) }}
        </span>
        <svg width="22" height="10" viewBox="0 0 22 10" fill="none" aria-hidden="true">
          <path d="M0,5 C5,0 8,10 11,5 S17,0 22,5" stroke="var(--accent)" stroke-width="2" />
        </svg>
        <span
          class="avatar"
          :class="{ away: !home.partnerOnline }"
          :style="{ color: partnerTint.ink, boxShadow: `inset 0 0 0 1.5px ${partnerTint.ring}` }"
        >
          {{ paired ? initial(P) : '?' }}
        </span>
      </div>
      <span :key="home.activity" class="presence-text" :class="{ active: !!home.activity }">{{ presence }}</span>
      <span
        class="dot"
        :class="{ on: paired && home.partnerOnline }"
        :style="{ background: paired && home.partnerOnline ? partnerTint.ring : undefined }"
      />
    </div>

    <div class="scroll">
      <div class="turn">
        <h1 class="turn-title">{{ title }}</h1>
        <p class="turn-sub">{{ sub }}</p>
      </div>

      <p v-if="r && r.i_sealed && away" class="sealed-for">
        <span class="sdot" />Sealed for {{ P }} · keeps for {{ hoursLeft }}
      </p>

      <button ref="deck" class="deck" type="button" :aria-label="drawLabel" @click="draw">
        <span class="card back a" />
        <span class="card back b" />
        <span class="card front">
          <span class="qmark">?</span>
          <KnotTie :w="34" mode="static" :stroke-width="12" halo="var(--surface2)" />
        </span>
      </button>

      <section class="group">
        <h2 class="label">How deep tonight</h2>
        <div class="segmented three" role="radiogroup" aria-label="Depth">
          <span class="pill" :style="{ transform: `translateX(${depthIndex * 100}%)` }" />
          <button
            v-for="d in DEPTHS"
            :key="d.id"
            type="button"
            role="radio"
            :aria-checked="home.settings.depth === d.id"
            :class="{ on: home.settings.depth === d.id }"
            :disabled="!paired"
            @click="home.setDepth(d.id)"
          >
            {{ d.label }}
          </button>
        </div>
      </section>

      <section class="group">
        <h2 class="label">What's in the hat · shared</h2>
        <div class="chips">
          <button
            class="random"
            :class="{ on: home.settings.random }"
            type="button"
            :aria-pressed="home.settings.random"
            :disabled="!paired"
            @click="home.toggleRandom()"
          >
            Random
          </button>
          <button
            v-for="c in chips"
            :key="c.id + (home.flash === c.id ? '-flash' : '')"
            class="chip"
            :class="{ on: c.on, struck: c.struck, waiting: c.waiting, flash: home.flash === c.id }"
            :style="{ '--flash': partnerTint.ring }"
            type="button"
            :aria-pressed="c.on"
            :disabled="!paired"
            @click="home.tapCategory(c.id)"
          >
            <span class="chip-dot" :style="{ background: c.dot }" />
            <span class="chip-label">{{ c.label }}</span>
            <span v-if="c.note" class="chip-note">{{ c.note }}</span>
          </button>
        </div>
        <p class="summary">{{ home.summary }}</p>
      </section>

      <details class="depths">
        <summary>
          <span>What do the depths mean?</span>
          <ChevronDown class="chev" :size="18" :stroke-width="1.75" />
        </summary>
        <dl>
          <template v-for="d in DEPTH_NOTES" :key="d.id">
            <dt :class="{ now: home.settings.depth === d.id }">{{ d.label }}</dt>
            <dd>{{ d.text }}</dd>
          </template>
        </dl>
        <p class="depth-note">
          Depth works the same in every category. In Spicy: Light is flirty, Medium is what you really like, Deep
          is what you really want.
        </p>
      </details>
    </div>

    <button
      class="btn draw"
      type="button"
      :class="{ waiting: paired && !r && !canDraw }"
      :disabled="game.busy"
      @click="draw"
    >
      {{ drawLabel }}
    </button>
  </main>
</template>

<style scoped>
.home {
  height: 100dvh;
  max-width: 480px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: max(58px, calc(var(--safe-top) + 10px)) 20px max(40px, calc(var(--safe-bottom) + 8px));
  animation: fadeIn calc(0.6s * var(--m)) ease both;
}

/* Header */
.top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
}
.wordmark {
  font: italic 500 28px/1 var(--serif);
  color: var(--accentInk);
}
.menu {
  width: 44px;
  height: 44px;
  border-radius: 22px;
  border: 1px solid var(--line);
  background: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 0;
}
.menu span {
  width: 16px;
  height: 1.5px;
  background: var(--ink);
}
.menu span:last-child {
  width: 10px;
}

/* Presence */
.presence {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 30px;
}
.pair-avatars {
  display: flex;
  align-items: center;
  flex: none;
}
.avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--surface2);
  display: grid;
  place-items: center;
  font: italic 500 17px/1 var(--serif);
  transition: opacity 0.3s;
}
.avatar.away {
  opacity: 0.5;
}
.presence-text {
  flex: 1;
  min-width: 0;
  font: 500 13px/1.2 var(--sans);
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.presence-text.active {
  color: var(--ink);
  animation: fadeIn 0.4s ease both;
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex: none;
  background: var(--line);
}
.dot.on {
  animation: glow 2s ease-in-out infinite;
}

/* Scrolling middle */
.scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: none;
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin: 0 -20px;
  padding: 2px 20px 4px;
}
.scroll::-webkit-scrollbar {
  display: none;
}
.turn {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.turn-title {
  margin: 0;
  font: 500 32px/1.05 var(--serif);
  text-wrap: balance;
}
.turn-sub {
  margin: 0;
  font: 400 14px/1.45 var(--sans);
  color: var(--muted);
  text-wrap: pretty;
}

/* Deck */
.deck {
  position: relative;
  height: 150px;
  border: none;
  background: none;
  padding: 0;
  flex: none;
}
.card {
  position: absolute;
  left: 50%;
  top: 6px;
  margin-left: -52px;
  width: 104px;
  height: 138px;
  border-radius: 16px;
}
.card.back {
  background: var(--surface);
  border: 1px solid var(--line);
}
.card.a {
  transform: rotate(-7deg);
}
.card.b {
  transform: rotate(7deg);
}
.card.front {
  background: linear-gradient(160deg, var(--surface2), var(--surface));
  border: 1.5px solid var(--accent2);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: 0 18px 40px -16px var(--glow);
  animation: breathe calc(5s * var(--m)) ease-in-out infinite;
}
.qmark {
  font: italic 500 50px/1 var(--serif);
  color: var(--accentInk);
}

/* Groups */
.group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.label {
  margin: 0;
  font: 700 11px/1 var(--sans);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted);
}

/* Segmented control (depth) */
.segmented {
  position: relative;
  display: grid;
  height: 46px;
  border-radius: 23px;
  background: var(--surface);
  padding: 4px;
}
.segmented.three {
  grid-template-columns: repeat(3, 1fr);
}
.segmented .pill {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 4px;
  width: calc((100% - 8px) / 3);
  border-radius: 19px;
  background: var(--accent);
  transition: transform 0.4s cubic-bezier(0.3, 1.3, 0.5, 1);
}
.segmented button {
  position: relative;
  z-index: 1;
  border: none;
  background: none;
  border-radius: 22px;
  min-height: 38px;
  font: 600 14px/1 var(--sans);
  color: var(--muted);
  transition: color 0.3s;
}
.segmented button.on {
  color: var(--onAccent);
}

/* Chips */
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.random {
  min-height: 40px;
  padding: 0 16px;
  border-radius: 20px;
  border: 1px dashed var(--line);
  background: transparent;
  color: var(--muted);
  font: 700 13px/1 var(--sans);
  transition: all 0.2s;
}
.random.on {
  border: 1.5px solid var(--accent);
  background: var(--accent);
  color: var(--onAccent);
}
.chip {
  min-height: 40px;
  padding: 0 14px;
  border-radius: 20px;
  display: flex;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--muted);
  font: 600 13px/1 var(--sans);
  transition: all 0.2s;
}
.chip.on {
  border: 1.5px solid var(--accent);
  background: var(--surface2);
  color: var(--ink);
}
.chip.waiting {
  border: 1.5px dashed var(--accent);
}
.chip.struck {
  opacity: 0.6;
}
.chip.struck .chip-label {
  text-decoration: line-through;
}
.chip.flash {
  animation: chipFlash 1.2s ease 2;
}
.chip-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: none;
  opacity: 0.45;
}
.chip.on .chip-dot {
  opacity: 1;
}
.chip-note {
  font: 500 11px/1 var(--sans);
  color: var(--muted);
}
.summary {
  margin: 0;
  font: italic 400 17px/1.3 var(--serif);
  color: var(--muted);
}

/* Sealed-for note */
.sealed-for {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 16px;
  background: var(--surface);
  font: 500 13px/1.3 var(--sans);
  animation: popIn 0.5s ease both;
}
.sdot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  flex: none;
}

/* Depth explainer */
.depths {
  border-radius: 18px;
  background: var(--surface);
  padding: 0 16px;
  flex: none;
}
.depths summary {
  list-style: none;
  min-height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font: 600 14px/1 var(--sans);
  cursor: pointer;
}
.depths summary::-webkit-details-marker {
  display: none;
}
.chev {
  color: var(--muted);
  transition: transform 0.25s;
}
.depths[open] .chev {
  transform: rotate(180deg);
}
.depths dl {
  margin: 0 0 6px;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px 14px;
}
.depths dt {
  font: 700 12px/1.4 var(--sans);
  letter-spacing: 0.06em;
  color: var(--muted);
}
.depths dt.now {
  color: var(--accentInk);
}
.depths dd {
  margin: 0;
  font: 400 14px/1.45 var(--sans);
  color: var(--ink);
}
.depth-note {
  margin: 4px 0 16px;
  font: italic 400 16px/1.35 var(--serif);
  color: var(--muted);
}

/* Draw */
.draw {
  flex: none;
}
.draw.waiting {
  opacity: 0.45;
}

button:disabled {
  cursor: default;
}

@keyframes glow {
  0%, 100% { filter: drop-shadow(0 0 3px var(--glow)); }
  50% { filter: drop-shadow(0 0 14px var(--accent)); }
}
@keyframes breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}
@keyframes popIn {
  0% { opacity: 0; transform: scale(0.6); }
  70% { opacity: 1; transform: scale(1.08); }
  100% { opacity: 1; transform: none; }
}
@keyframes chipFlash {
  0% { box-shadow: 0 0 0 0 var(--flash); }
  30% { box-shadow: 0 0 0 4px var(--flash); }
  100% { box-shadow: 0 0 0 0 transparent; }
}
</style>
