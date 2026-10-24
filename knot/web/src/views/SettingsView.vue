<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Check, ChevronLeft, ChevronRight, Copy, Pencil, Share } from 'lucide-vue-next'
import KnotTie from '@/components/KnotTie.vue'
import { useSwipe } from '@/lib/swipe'
import { api, ApiError } from '@/lib/api'
import { loadKey } from '@/lib/keystore'
import { disablePush, enablePush, markAskedForPush, pushState, type PushState } from '@/lib/push'
import { PRESETS, swatchBg, swatchRing } from '@/lib/theme'
import { toast } from '@/lib/toast'
import type { InviteOut, InviteStatus } from '@/lib/types'
import { useAuth } from '@/stores/auth'
import { useKnot } from '@/stores/knot'
import { useTheme } from '@/stores/theme'

const auth = useAuth()
const knot = useKnot()
const theme = useTheme()
const router = useRouter()

const me = computed(() => auth.me)

// Back to wherever Settings was opened from (home, or the middle of a round). Swipe right too.
function goBack() {
  if (window.history.state?.back) router.back()
  else router.replace({ name: 'home' })
}
const page = ref<HTMLElement | null>(null)
useSwipe(page, { right: goBack })
const P = computed(() => me.value?.partner?.display_name ?? 'They')
const isOwnerUnpaired = computed(() => me.value?.role === 'owner' && !me.value.pair_complete)

// ── Theme ──
const hueLabel = computed(() => {
  const p = PRESETS.find((x) => x.id === theme.prefs.preset)
  return p ? `${p.label} · ${theme.prefs.accentHue}°` : `${theme.prefs.accentHue}°`
})
function onHue(e: Event) {
  theme.setAccent(Number((e.target as HTMLInputElement).value))
}

// ── Name ──
const editingName = ref(false)
const newName = ref('')
function startEditName() {
  newName.value = me.value?.display_name ?? ''
  editingName.value = true
}
async function saveName() {
  const v = newName.value.trim()
  if (!v) return
  try {
    await auth.updateMe({ display_name: v })
    editingName.value = false
    toast('Saved.')
  } catch {
    toast('Couldn’t save that. Try again.')
  }
}

// ── Pairing code (owner, until paired) ──
const invite = ref<InviteOut | null>(null)
const pendingUntil = ref<string | null>(null)
const making = ref(false)
const copied = ref(false)
const canShare = typeof navigator.share === 'function'
const expiresText = computed(() =>
  pendingUntil.value
    ? new Date(pendingUntil.value).toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })
    : '',
)

async function refreshInvite() {
  try {
    pendingUntil.value = (await api.get<InviteStatus>('/invites/status')).pending_invite_expires_at
  } catch {
    /* not critical */
  }
}
async function makeInvite() {
  making.value = true
  try {
    invite.value = await api.post<InviteOut>('/invites')
    pendingUntil.value = invite.value.expires_at
    copied.value = false
  } catch (e) {
    toast(e instanceof ApiError ? e.message : 'Couldn’t make a code. Try again.')
  } finally {
    making.value = false
  }
}
async function copyInvite() {
  if (!invite.value) return
  try {
    await navigator.clipboard.writeText(invite.value.code)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    toast('Couldn’t copy. Press and hold the code instead.')
  }
}
async function shareInvite() {
  if (invite.value) await navigator.share({ text: invite.value.code }).catch(() => {})
}
async function cancelInvite() {
  try {
    await api.del('/invites')
    invite.value = null
    pendingUntil.value = null
    toast('That code no longer works.')
  } catch {
    toast('Couldn’t cancel it. Try again.')
  }
}

// ── Phrase on this phone ──
const remembered = ref<boolean | null>(null)
async function lockNow() {
  await knot.forget()
  toast('Locked. You’ll need the phrase to get back in.')
  router.replace({ name: 'unlock' })
}

// ── Notifications on this phone ──
const pushNow = ref<PushState>('off')
const pushBusy = ref(false)
const pushOn = computed(() => pushNow.value === 'on')
const pushNote = computed(() =>
  pushNow.value === 'needs-install'
    ? 'Add it to your Home Screen first'
    : pushNow.value === 'denied'
      ? 'Turned off in your phone’s Settings › Notifications › W.W.'
      : pushNow.value === 'unsupported'
        ? 'Not available in this browser'
        : '',
)
async function togglePush() {
  pushBusy.value = true
  try {
    if (pushOn.value) {
      await disablePush()
      pushNow.value = 'off'
      toast('Tugs off on this phone.')
    } else {
      markAskedForPush()
      pushNow.value = await enablePush()
      if (pushNow.value === 'on') toast(`Tugs on. Only ever from ${P.value}.`)
    }
  } catch {
    toast('That didn’t work. Try again.')
  } finally {
    pushBusy.value = false
  }
}

async function signOut() {
  await auth.logout()
  toast('Signed out. The door is closed.')
  router.replace({ name: 'door' })
}

onMounted(async () => {
  remembered.value = (await loadKey()) !== null
  pushState().then((s) => (pushNow.value = s))
  if (isOwnerUnpaired.value) refreshInvite()
})
</script>

<template>
  <main v-if="me" ref="page" class="settings">
    <div class="head">
      <button class="back" type="button" aria-label="Back" @click="goBack">
        <ChevronLeft :size="22" :stroke-width="1.75" />
      </button>
      <h1 class="title">Settings</h1>
    </div>

    <!-- Live preview of your palette -->
    <section class="preview">
      <div class="preview-top">
        <span class="eyebrow">Live preview</span>
        <KnotTie :w="34" mode="static" :stroke-width="12" />
      </div>
      <p class="preview-q">A slow kiss, or a surprise one?</p>
      <div class="preview-opts">
        <span class="opt on">Slow</span>
        <span class="opt">Surprise</span>
      </div>
    </section>

    <section class="group">
      <h2 class="label">Mode</h2>
      <div class="segmented two" role="radiogroup" aria-label="Mode">
        <span class="pill" :style="{ transform: `translateX(${theme.prefs.mode === 'night' ? 0 : 100}%)` }" />
        <button
          v-for="m in [{ id: 'night', label: 'Night' }, { id: 'candle', label: 'Candle' }] as const"
          :key="m.id"
          type="button"
          role="radio"
          :aria-checked="theme.prefs.mode === m.id"
          :class="{ on: theme.prefs.mode === m.id }"
          @click="theme.setMode(m.id)"
        >
          {{ m.label }}
        </button>
      </div>
    </section>

    <section class="group">
      <h2 class="label">Palette · just yours</h2>
      <div class="presets">
        <button
          v-for="p in PRESETS"
          :key="p.id"
          class="preset"
          :class="{ on: theme.prefs.preset === p.id }"
          type="button"
          :aria-pressed="theme.prefs.preset === p.id"
          @click="theme.setPreset(p.id)"
        >
          <span class="swatch" :style="{ background: swatchBg(p.base, theme.prefs.mode) }">
            <span class="swatch-ring" :style="{ borderColor: swatchRing(p.accent) }" />
          </span>
          <span class="preset-label">{{ p.label }}</span>
        </button>
      </div>
      <div class="hue">
        <div class="hue-top">
          <span>Custom accent</span>
          <span class="muted">{{ hueLabel }}</span>
        </div>
        <input
          type="range"
          min="0"
          max="359"
          :value="theme.prefs.accentHue"
          aria-label="Accent hue"
          @input="onHue"
        />
        <div class="hue-bar" />
      </div>
      <p class="note left">{{ P }} picks their own. Your accent tints your answer cards at the reveal.</p>
    </section>

    <section class="card">
      <p class="label">You appear as</p>
      <form v-if="editingName" class="name-row" @submit.prevent="saveName">
        <input v-model="newName" class="field" maxlength="40" aria-label="Your name" autofocus />
        <button class="btn small" type="submit">Save</button>
      </form>
      <div v-else class="name-row">
        <span class="name">{{ me.display_name }}</span>
        <button class="icon" type="button" aria-label="Change name" @click="startEditName">
          <Pencil :size="16" :stroke-width="1.75" />
        </button>
      </div>
    </section>

    <section v-if="isOwnerUnpaired" class="card invite">
      <p class="label">Pairing code</p>
      <template v-if="invite">
        <p class="code" aria-live="polite">{{ invite.code }}</p>
        <div class="row">
          <button class="btn ghost small" type="button" @click="copyInvite">
            <component :is="copied ? Check : Copy" :size="16" /> {{ copied ? 'Copied' : 'Copy' }}
          </button>
          <button v-if="canShare" class="btn ghost small" type="button" @click="shareInvite">
            <Share :size="16" /> Share
          </button>
        </div>
        <p class="note">Works once, until {{ expiresText }}. This is the only time it's shown.</p>
      </template>
      <p v-else-if="pendingUntil" class="sub small">
        A code is out there, valid until {{ expiresText }}. Codes are never shown twice, so if it's lost, make a new
        one. The old one stops working.
      </p>
      <p v-else class="sub small">Make a code and give it to the one person who should join you.</p>
      <button class="btn" type="button" :disabled="making" @click="makeInvite">
        {{ making ? 'Making…' : pendingUntil ? 'Make a new code' : 'Make a pairing code' }}
      </button>
      <button v-if="pendingUntil" class="btn link" type="button" @click="cancelInvite">Cancel the code</button>
    </section>

    <section class="list">
      <button type="button" class="toggle-row" :disabled="pushBusy || pushNote !== ''" @click="togglePush">
        <span class="row-text">
          <span>Tugs and turn alerts</span>
          <span v-if="pushNote" class="muted small">{{ pushNote }}</span>
        </span>
        <span class="track" :class="{ on: pushOn }"><span class="knob" /></span>
      </button>
      <button type="button" @click="router.push({ name: 'unlock', query: { mode: 'change' } })">
        <span>Retie the knot</span><ChevronRight :size="18" class="muted" />
      </button>
      <button type="button" @click="lockNow">
        <span>Lock this phone</span>
        <span class="muted small">{{ remembered ? 'Remembered here' : 'Not remembered' }}</span>
      </button>
      <button type="button" @click="signOut">
        <span>Sign out</span><span class="muted small">{{ me.display_name }}</span>
      </button>
    </section>

    <p class="footer">There's no history here. On purpose.</p>
  </main>
</template>

<style scoped>
.settings {
  max-width: 480px;
  margin: 0 auto;
  padding: max(58px, calc(var(--safe-top) + 10px)) 22px max(48px, calc(var(--safe-bottom) + 14px));
  display: flex;
  flex-direction: column;
  gap: 22px;
  animation: fadeIn 0.5s ease both;
}
.head {
  display: flex;
  align-items: center;
  gap: 14px;
}
.head .title {
  font-size: 34px;
  line-height: 1;
}

.preview {
  border-radius: 24px;
  padding: 18px;
  background: var(--bg);
  box-shadow: inset 0 0 0 1px var(--line);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.preview-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.preview-q {
  margin: 0;
  font: 500 24px/1.15 var(--serif);
}
.preview-opts {
  display: flex;
  gap: 8px;
}
.opt {
  flex: 1;
  height: 44px;
  border-radius: 14px;
  border: 1px solid var(--line);
  display: grid;
  place-items: center;
  font: 600 14px/1 var(--sans);
}
.opt.on {
  background: var(--accent);
  color: var(--onAccent);
  border-color: transparent;
}

.group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.label {
  margin: 0;
  font: 700 11px/1 var(--sans);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted);
}

.segmented {
  position: relative;
  display: grid;
  height: 50px;
  border-radius: 25px;
  background: var(--surface);
  padding: 4px;
}
.segmented.two {
  grid-template-columns: 1fr 1fr;
}
.segmented .pill {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 4px;
  width: calc((100% - 8px) / 2);
  border-radius: 21px;
  background: var(--accent);
  transition: transform 0.4s cubic-bezier(0.3, 1.3, 0.5, 1);
}
.segmented button {
  position: relative;
  z-index: 1;
  border: none;
  background: none;
  font: 600 14px/1 var(--sans);
  color: var(--muted);
  transition: color 0.3s;
}
.segmented button.on {
  color: var(--onAccent);
}

.presets {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.preset {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 12px 0;
  border-radius: 18px;
  border: 1px solid var(--line);
  background: transparent;
  transition: all 0.2s;
}
.preset.on {
  border: 1.5px solid var(--accent);
  background: var(--surface);
}
.swatch {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  box-shadow: inset 0 0 0 1px var(--line);
  transition: transform 0.3s cubic-bezier(0.3, 1.4, 0.5, 1);
}
.preset.on .swatch {
  transform: scale(1.06);
}
.swatch-ring {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 4px solid;
}
.preset-label {
  font: 600 13px/1 var(--sans);
}

.hue {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  border-radius: 18px;
  background: var(--surface);
}
.hue-top {
  display: flex;
  justify-content: space-between;
  font: 600 13px/1 var(--sans);
}
.hue input {
  width: 100%;
  height: 28px;
  accent-color: var(--accent);
}
.hue-bar {
  height: 6px;
  border-radius: 3px;
  background: linear-gradient(
    90deg,
    oklch(0.75 0.11 0),
    oklch(0.75 0.11 60),
    oklch(0.75 0.11 120),
    oklch(0.75 0.11 180),
    oklch(0.75 0.11 240),
    oklch(0.75 0.11 300),
    oklch(0.75 0.11 359)
  );
}
.muted {
  color: var(--muted);
}
.small {
  font-size: 14px;
}
.note.left {
  text-align: left;
}

.icon {
  width: 44px;
  height: 44px;
  border-radius: 22px;
  border: 1px solid var(--line);
  background: none;
  display: grid;
  place-items: center;
  padding: 0;
}
.name-row {
  margin-top: 12px;
  display: flex;
  gap: 10px;
  align-items: center;
}
.name-row .field {
  height: 48px;
  font-size: 16px;
}
.name {
  flex: 1;
  font: 500 26px/1.1 var(--serif);
}
.btn.small {
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 14px;
}
.name-row .btn.small {
  width: auto;
  padding: 0 20px;
}
.invite {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.code {
  margin: 0;
  text-align: center;
  font: 600 32px/1.2 ui-monospace, Menlo, monospace;
  letter-spacing: 0.12em;
  color: var(--accentInk);
  user-select: all;
  -webkit-user-select: all;
}
.row {
  display: flex;
  gap: 10px;
}

.list {
  display: flex;
  flex-direction: column;
  border-radius: 22px;
  background: var(--surface);
  overflow: hidden;
}
.list button {
  min-height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  border: none;
  border-bottom: 1px solid var(--line);
  background: none;
  font: 500 16px/1 var(--sans);
  text-align: left;
}
.list button:last-child {
  border-bottom: none;
}
.toggle-row {
  gap: 12px;
}
.toggle-row:disabled {
  cursor: default;
}
.row-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
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
.footer {
  margin: 0;
  padding-top: 6px;
  text-align: center;
  font: italic 400 20px/1.3 var(--serif);
  color: var(--muted);
}
</style>
