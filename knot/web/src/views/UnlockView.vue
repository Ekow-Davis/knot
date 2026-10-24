<script setup lang="ts">
/**
 * Tie the knot (first time), open it (enter the phrase), or retie it (?mode=change).
 * The rings drift together as the phrase gets longer, wobble apart on a wrong phrase,
 * and turn into the rope knot when it's right.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Eye, EyeOff } from 'lucide-vue-next'
import BackButton from '@/components/BackButton.vue'
import KnotTie from '@/components/KnotTie.vue'
import { ApiError } from '@/lib/api'
import { shouldAskForPush } from '@/lib/push'
import { toast } from '@/lib/toast'
import { useAuth } from '@/stores/auth'
import { AlreadyTied, PhraseMismatch, useKnot } from '@/stores/knot'

const auth = useAuth()
const knot = useKnot()
const route = useRoute()
const router = useRouter()

// Decided once when the screen opens, so it doesn't flip mid-animation once the knot is open.
type Mode = 'tie' | 'unlock' | 'change'
const mode = ref<Mode>(
  route.query.mode === 'change' && knot.status === 'unlocked' ? 'change' : knot.status === 'untied' ? 'tie' : 'unlock',
)
// The other phone tied it while this one was showing "Tie the knot.": switch to entering it.
watch(
  () => knot.status,
  (s) => {
    if (mode.value === 'tie' && s === 'locked' && state.value !== 'working') {
      mode.value = 'unlock'
      note.value = `${partner.value} just tied it. Enter the phrase you two chose.`
      phrase.value = ''
    }
  },
)
const isChange = computed(() => mode.value === 'change')
const isNew = computed(() => mode.value !== 'unlock')
const partner = computed(() => auth.me?.partner?.display_name ?? 'them')

const phrase = ref('')
const show = ref(false)
const remember = ref(true)
const state = ref<'idle' | 'working' | 'wrong' | 'tied'>('idle')
const note = ref<string | null>(null) // extra line, e.g. "Ama tied it first."
const input = ref<HTMLInputElement | null>(null)

const MIN = 6
const ready = computed(() => phrase.value.trim().length >= MIN && state.value !== 'working' && state.value !== 'tied')

const title = computed(() => (isChange.value ? 'Retie the knot.' : 'Tie the knot.'))
const sub = computed(() => {
  if (isChange.value) return 'Choose a new phrase. Anything still sealed under the old one will come undone.'
  if (mode.value === 'tie') return 'Pick a phrase only you two know. Three or four words works well. Every answer is locked with it.'
  if (knot.changedElsewhere) return `${partner.value} changed the phrase. Enter the new one.`
  return "Your shared phrase, please. It unlocks tonight's answers."
})
const hint = computed(() => {
  if (state.value === 'wrong') return null
  if (state.value === 'working') return isNew.value ? 'Tying…' : 'Checking…'
  if (state.value === 'tied') return 'Tied.'
  const n = phrase.value.trim().length
  if (n === 0) return ''
  if (!isNew.value) return '' // when entering an existing phrase, length hints would be a clue
  return n < MIN ? 'A little longer…' : n < 10 ? 'That will hold.' : 'Good and tight.'
})

// Rings: apart when empty, closer with each character, overlapping when tied.
const offset = computed(() =>
  state.value === 'tied' ? -10 : state.value === 'wrong' ? 26 : Math.max(0, 40 - phrase.value.length * 5),
)

let timer: ReturnType<typeof setTimeout> | undefined
onBeforeUnmount(() => clearTimeout(timer))
const wait = (ms: number) => new Promise<void>((r) => (timer = setTimeout(r, ms)))
const motion = () => parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--m')) || 1

function onInput(e: Event) {
  phrase.value = (e.target as HTMLInputElement).value
  if (state.value === 'wrong') state.value = 'idle'
}

async function submit() {
  if (!ready.value) {
    if (phrase.value.trim().length < MIN && phrase.value.length > 0) toast('A little longer, so it holds.')
    return
  }
  state.value = 'working'
  note.value = null
  try {
    if (mode.value === 'change') await knot.retie(phrase.value)
    else if (mode.value === 'tie') await knot.tie(phrase.value, remember.value)
    else await knot.unlock(phrase.value, remember.value)
  } catch (e) {
    if (e instanceof PhraseMismatch) {
      state.value = 'wrong'
      input.value?.select()
      return
    }
    state.value = 'idle'
    if (e instanceof AlreadyTied) {
      // They tied it a moment before us. If we typed the same phrase, just open it.
      mode.value = 'unlock'
      state.value = 'working'
      try {
        await knot.unlock(phrase.value, remember.value)
      } catch (err) {
        state.value = err instanceof PhraseMismatch ? 'wrong' : 'idle'
        note.value = `${partner.value} tied it first, with a different phrase. Enter theirs.`
        input.value?.select()
        return
      }
      // Same phrase: fall through to the tied animation below.
    } else if (e instanceof ApiError && e.code === 'version_changed') {
      toast(`${partner.value} just changed it. Use their new phrase.`)
      await knot.load()
      mode.value = knot.status === 'unlocked' ? 'change' : 'unlock'
      return
    } else {
      toast(e instanceof ApiError && e.code === 'offline' ? 'No connection. Try again in a moment.' : 'Something went wrong. Try again.')
      return
    }
  }

  state.value = 'tied'
  const changed = mode.value === 'change'
  const first = mode.value === 'tie'
  phrase.value = ''
  await wait(2600 * motion())
  if (changed) toast(`Knot retied. Tell ${partner.value} in person.`)
  else if (first) toast(`Tied. Tell ${partner.value} the phrase in person, not by text.`)
  else toast(`Welcome back, ${auth.me?.display_name ?? 'you'}.`)
  router.replace({ name: changed ? 'settings' : shouldAskForPush() ? 'notify' : 'home' })
}
</script>

<template>
  <main class="screen unlock">
    <BackButton v-if="isChange" :to="{ name: 'settings' }" />
    <div v-else class="spacer" />

    <div class="heading center">
      <h1 class="title big">{{ title }}</h1>
      <p class="sub narrow">{{ note ?? sub }}</p>
    </div>

    <div class="stage" aria-hidden="true">
      <div class="rings" :class="state">
        <span class="ring left" :style="{ transform: `translateX(${-offset}px)` }" />
        <span class="ring right" :style="{ transform: `translateX(${offset}px)` }" />
      </div>
      <div v-if="state === 'tied'" class="tied">
        <KnotTie :w="200" mode="tie" :delay="0.25" glow />
      </div>
    </div>

    <form class="phrase" @submit.prevent="submit">
      <div class="field-wrap">
        <input
          ref="input"
          :value="phrase"
          :type="show ? 'text' : 'password'"
          class="field"
          placeholder="your shared phrase"
          autocomplete="off"
          autocapitalize="none"
          autocorrect="off"
          spellcheck="false"
          enterkeyhint="done"
          aria-label="Shared phrase"
          :disabled="state === 'working' || state === 'tied'"
          @input="onInput"
        />
        <button
          class="eye"
          type="button"
          :aria-label="show ? 'Hide phrase' : 'Show phrase'"
          :aria-pressed="show"
          @click="show = !show"
        >
          <component :is="show ? EyeOff : Eye" :size="20" :stroke-width="1.75" />
        </button>
      </div>
      <p class="hint" role="status">
        <span v-if="state === 'wrong'" class="wrong">That's not the phrase you two tied.</span>
        <span v-else class="ok">{{ hint }}</span>
      </p>
    </form>

    <button
      v-if="!isChange"
      class="toggle"
      type="button"
      role="switch"
      :aria-checked="remember"
      @click="remember = !remember"
    >
      <span>Remember on this phone</span>
      <span class="track" :class="{ on: remember }"><span class="knob" /></span>
    </button>
    <p v-else class="card change-note">Both phones need the new phrase. Tell {{ partner }} in person, not by text.</p>

    <div class="grow" />

    <div class="actions">
      <button class="btn" type="button" :disabled="!ready" @click="submit">
        {{ state === 'working' ? (isNew ? 'Tying…' : 'Checking…') : isChange ? 'Retie it' : 'Tie it' }}
      </button>
      <p class="note">If you forget it, anything still sealed can't be opened. Answers are deleted after each reveal anyway.</p>
    </div>
  </main>
</template>

<style scoped>
.unlock {
  gap: 20px;
}
.spacer {
  height: 44px;
}
.center {
  text-align: center;
  align-items: center;
}
.big {
  font-size: 42px;
  line-height: 1;
}
.narrow {
  max-width: 300px;
}

/* ── Rings ── */
.stage {
  position: relative;
  height: 130px;
  display: grid;
  place-items: center;
}
.rings {
  position: relative;
  width: 140px;
  height: 84px;
  animation: breathe calc(4s * var(--m)) ease-in-out infinite;
}
.rings.wrong {
  animation: wobble 0.7s 0.3s ease;
}
.rings.tied {
  animation: none;
}
.ring {
  position: absolute;
  top: 0;
  width: 84px;
  height: 84px;
  border-radius: 50%;
  border: 5px solid var(--accent);
  transition: transform 0.35s cubic-bezier(0.3, 1.4, 0.5, 1);
}
.ring.left {
  left: 0;
}
.ring.right {
  right: 0;
}
.rings.wrong .left {
  animation: failL 0.9s ease both;
}
.rings.wrong .right {
  animation: failR 0.9s ease both;
}
.rings.tied .ring {
  animation: mergeOut 0.5s 0.15s ease forwards;
}
.rings.working {
  animation: breathe calc(1.2s * var(--m)) ease-in-out infinite;
}
.tied {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
}

/* ── Phrase field with the eye ── */
.phrase {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.field-wrap {
  position: relative;
}
.field-wrap .field {
  text-align: center;
  font-size: 20px;
  letter-spacing: 0.12em;
  padding: 0 56px; /* room for the eye on the right, balanced on the left */
}
.field-wrap .field[type='text'] {
  letter-spacing: 0.04em;
}
.eye {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  width: 44px;
  height: 44px;
  border: none;
  border-radius: 14px;
  background: none;
  color: var(--muted);
  display: grid;
  place-items: center;
  padding: 0;
}
.eye[aria-pressed='true'] {
  color: var(--accentInk);
}
.hint {
  margin: 0;
  min-height: 18px;
  text-align: center;
  font: 500 13px/1.4 var(--sans);
}
.hint .ok {
  color: var(--accentInk);
}
.hint .wrong {
  color: var(--warn);
}

/* ── Remember switch ── */
.toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 56px;
  padding: 0 16px 0 18px;
  border-radius: 18px;
  border: none;
  background: var(--surface);
  font: 500 15px/1.2 var(--sans);
  text-align: left;
}
.track {
  position: relative;
  width: 51px;
  height: 31px;
  border-radius: 16px;
  background: var(--line);
  transition: background 0.25s;
  flex: none;
}
.track.on {
  background: var(--accent);
}
.knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 27px;
  height: 27px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 2px 6px rgb(0 0 0 / 0.25);
  transition: transform 0.3s cubic-bezier(0.3, 1.4, 0.5, 1);
}
.track.on .knob {
  transform: translateX(20px);
}
.change-note {
  margin: 0;
  padding: 14px 18px;
  border-radius: 18px;
  font: 500 14px/1.45 var(--sans);
  text-wrap: pretty;
}
.actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

@keyframes breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}
@keyframes wobble {
  0%, 100% { transform: rotate(0); }
  20% { transform: rotate(-5deg); }
  40% { transform: rotate(4deg); }
  60% { transform: rotate(-3deg); }
  80% { transform: rotate(2deg); }
}
@keyframes failL {
  0% { transform: translateX(0); }
  35% { transform: translateX(16px); }
  60% { transform: translateX(-34px) rotate(-10deg); }
  80% { transform: translateX(-20px); }
  100% { transform: translateX(-26px); }
}
@keyframes failR {
  0% { transform: translateX(0); }
  35% { transform: translateX(-16px); }
  60% { transform: translateX(34px) rotate(10deg); }
  80% { transform: translateX(20px); }
  100% { transform: translateX(26px); }
}
@keyframes mergeOut {
  0% { opacity: 1; }
  100% { transform: scale(0.4); opacity: 0; }
}
</style>
