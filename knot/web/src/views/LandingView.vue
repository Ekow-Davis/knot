<script setup lang="ts">
/**
 * The landing page: what she sees when the link opens in a browser (not from the Home Screen).
 * Explains Knot, promises privacy honestly, and shows install steps for exactly the browser
 * she's in. Inside Instagram/WhatsApp/etc. it shows "Open this in Safari first" instead.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import KnotTie from '@/components/KnotTie.vue'
import { chooseBrowserApp, detectPlatform, onInstallAvailable, promptInstall } from '@/lib/platform'
import { toast } from '@/lib/toast'

const router = useRouter()
const p = detectPlatform()

// ── Install steps for this exact browser ──
type Step = { text: string; bold?: string; after?: string; art: 'share' | 'dots' | 'plus' | 'icon' | 'menu' }
const steps = computed<Step[]>(() => {
  const open: Step = { text: 'Open', bold: 'W.W.', after: ' from its icon', art: 'icon' }
  if (p.kind === 'safari' && p.ipad)
    return [
      { text: 'Tap', bold: 'Share', after: ' at the top, beside the address bar', art: 'share' },
      { text: 'Choose', bold: 'Add to Home Screen', art: 'plus' },
      open,
    ]
  if (p.kind === 'safari' && p.safari >= 26)
    return [
      { text: 'Tap', bold: '•••', after: ' beside the address bar', art: 'dots' },
      { text: 'Tap', bold: 'Share', art: 'share' },
      { text: 'Choose', bold: 'Add to Home Screen', after: ', keep “Open as Web App” on, then Add', art: 'plus' },
      open,
    ]
  if (p.kind === 'safari')
    return [
      { text: 'Tap', bold: 'Share', after: ' in the toolbar below', art: 'share' },
      { text: 'Choose', bold: 'Add to Home Screen', art: 'plus' },
      open,
    ]
  if (p.kind === 'iosother')
    return [
      { text: 'Tap', bold: 'Share', after: ' (in the address bar or the menu)', art: 'share' },
      { text: 'Choose', bold: 'Add to Home Screen', art: 'plus' },
      open,
    ]
  if (p.kind === 'android')
    return [
      { text: 'Tap', bold: '⋮', after: ' at the top right', art: 'menu' },
      { text: 'Choose', bold: 'Install app', after: ' (or Add to Home screen)', art: 'plus' },
      open,
    ]
  return []
})

const pointer = computed(() => {
  if (p.kind !== 'safari') return null
  if (p.ipad) return { text: 'Tap Share up here', where: 'top' }
  if (p.safari >= 26) return { text: 'Tap •••, then Share', where: 'bottom-right' }
  return { text: 'Tap Share, then Add to Home Screen', where: 'bottom' }
})

// ── Android's real install button ──
const canInstall = ref(false)
let stop: (() => void) | null = null
onMounted(() => (stop = onInstallAvailable((a) => (canInstall.value = a))))
onBeforeUnmount(() => stop?.())
async function install() {
  if (await promptInstall()) toast('Installed. Open it from your apps.')
}

// ── In-app browsers ──
const inAppHow = computed(() => {
  switch (p.app) {
    case 'instagram':
      return 'Tap ••• at the top right, then Open in external browser.'
    case 'facebook':
      return 'Tap ••• at the top right, then Open in external browser.'
    case 'snapchat':
      return 'Tap ••• at the top, then Open in Safari.'
    case 'tiktok':
      return 'Tap ••• at the top right, then Open in browser.'
    case 'whatsapp':
      return 'Tap the compass (or •••) and choose Open in Safari.'
    case 'twitter':
    case 'linkedin':
    case 'google':
      return 'Tap ••• or the share icon, then Open in Safari.'
    default:
      return 'Look for ••• or a compass icon and choose Open in Safari. Or copy the link and paste it into Safari.'
  }
})

async function copyLink() {
  try {
    await navigator.clipboard.writeText(location.origin + '/')
    toast(p.kind === 'desktop' ? 'Link copied. Send it to your phone.' : 'Link copied. Paste it into Safari.')
  } catch {
    toast('Press and hold the address at the top to copy it.')
  }
}

function openHere() {
  chooseBrowserApp()
  router.replace({ name: 'door' })
}
</script>

<template>
  <!-- ── Inside Instagram, WhatsApp, Snapchat… ── -->
  <main v-if="p.kind === 'inapp'" class="inapp">
    <div class="up-hint" aria-hidden="true"><span>↑</span><span>Tap up here</span></div>
    <div class="inapp-mid">
      <KnotTie :w="120" mode="tie" />
      <h1 class="title">Open this in Safari first.</h1>
      <p class="sub">This little browser can't add it to your Home Screen. {{ inAppHow }}</p>
    </div>
    <button class="btn" type="button" @click="copyLink">Copy link instead</button>
  </main>

  <!-- ── Everywhere else ── -->
  <main v-else class="landing">
    <section class="hero">
      <KnotTie :w="230" mode="tie" :delay="0.3" glow />
      <h1 class="name">Knot</h1>
      <p class="tagline">A quiet game for two people who already know each other by heart.</p>
      <span class="badge"><i />Private · made for exactly two</span>
    </section>

    <section class="how">
      <h2 class="label">How it works</h2>
      <div class="beat">
        <span class="num">1</span>
        <div>
          <p class="beat-title">Draw a card</p>
          <p class="beat-text">A question comes from a hidden deck. Nobody gets to browse it.</p>
        </div>
      </div>
      <div class="beat">
        <span class="num">2</span>
        <div>
          <p class="beat-title">Both answer in secret</p>
          <p class="beat-text">Your answer stays sealed until the other one has written theirs.</p>
        </div>
      </div>
      <div class="beat">
        <span class="num">3</span>
        <div>
          <p class="beat-title">Reveal together, then it's gone</p>
          <p class="beat-text">You both pull the rope at once. After you've seen it, it's deleted.</p>
        </div>
      </div>
    </section>

    <section class="privacy">
      <span class="lock" aria-hidden="true"><i /><b /></span>
      <h2 class="privacy-title">Private by design</h2>
      <p class="privacy-text">
        Answers are encrypted on your phone before they leave it. Once you've both seen them, they're deleted from the
        server.
      </p>
      <p class="privacy-fine">No history, no archive, nothing to scroll back through.</p>
    </section>

    <!-- Install -->
    <section v-if="p.kind === 'desktop'" class="install">
      <h2 class="install-title">Made for your phone</h2>
      <p class="sub">Open this link on your phone and put it on your Home Screen.</p>
      <button class="btn ghost" type="button" @click="copyLink">Copy the link</button>
    </section>

    <section v-else-if="p.kind === 'android' && canInstall" class="install">
      <h2 class="install-title">Keep it with your apps</h2>
      <p class="sub">One tap. No app store, no account to find.</p>
    </section>

    <section v-else class="install">
      <h2 class="install-title">Put it on your Home Screen</h2>
      <ol class="steps">
        <li v-for="(s, i) in steps" :key="i" class="step">
          <span class="step-num">{{ i + 1 }}</span>
          <span class="step-text">{{ s.text }} <b>{{ s.bold }}</b>{{ s.after }}</span>
          <span class="art" :class="s.art" aria-hidden="true">
            <template v-if="s.art === 'share'"><span class="share-box" /></template>
            <template v-else-if="s.art === 'dots'">•••</template>
            <template v-else-if="s.art === 'menu'">⋮</template>
            <template v-else-if="s.art === 'plus'">+</template>
            <img v-else src="/icons/apple-touch-icon.png" alt="" />
          </span>
        </li>
      </ol>
      <p v-if="p.kind === 'safari'" class="fine">
        No “Add to Home Screen”? You may be inside another app's browser. Look for the Safari compass and open it
        there.
      </p>
      <p v-if="p.kind === 'iosother'" class="fine">Safari works best for this, if you have the choice.</p>
    </section>

    <footer class="foot">
      <p class="fine">Opened from the Home Screen, it skips this page and goes straight in.</p>
      <button class="btn ghost" type="button" @click="openHere">Just open it here</button>
      <p class="fine small">Works in the browser too, but notifications need the Home Screen version.</p>
    </footer>

    <!-- Android: a real install button -->
    <div v-if="p.kind === 'android' && canInstall" class="android-bar">
      <button class="btn" type="button" @click="install">Install</button>
    </div>

    <!-- iPhone Safari: point at the real browser controls -->
    <div v-if="pointer" class="pointer" :class="pointer.where" aria-hidden="true">
      <span v-if="pointer.where === 'top'" class="tip-arrow up" />
      <span class="tip">{{ pointer.text }}</span>
      <span v-if="pointer.where !== 'top'" class="tip-arrow" />
    </div>
  </main>
</template>

<style scoped>
.landing {
  max-width: 480px;
  margin: 0 auto;
  padding: max(84px, calc(var(--safe-top) + 40px)) 26px calc(160px + var(--safe-bottom));
  display: flex;
  flex-direction: column;
  gap: 52px;
}

/* Hero */
.hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  text-align: center;
  animation: fadeIn 0.8s ease both;
}
.name {
  margin: 0;
  font: italic 500 64px/1 var(--serif);
  color: var(--accentInk);
}
.tagline {
  margin: 0;
  max-width: 300px;
  font: 500 24px/1.25 var(--serif);
  text-wrap: balance;
}
.badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 32px;
  padding: 0 14px;
  border-radius: 16px;
  border: 1px solid var(--line);
  font: 600 12px/1 var(--sans);
  color: var(--muted);
}
.badge i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
}

/* How it works */
.how {
  display: flex;
  flex-direction: column;
  gap: 22px;
}
.label {
  margin: 0;
  font: 700 11px/1 var(--sans);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted);
}
.beat {
  display: flex;
  gap: 18px;
  align-items: flex-start;
}
.num {
  width: 28px;
  flex: none;
  font: italic 500 44px/0.9 var(--serif);
  color: var(--accentInk);
}
.beat-title {
  margin: 0 0 6px;
  font: 600 17px/1.2 var(--sans);
}
.beat-text {
  margin: 0;
  font: 400 14px/1.5 var(--sans);
  color: var(--muted);
  text-wrap: pretty;
}

/* Privacy */
.privacy {
  border-radius: 26px;
  padding: 24px 22px;
  background: var(--surface);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.lock {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 22px;
}
.lock i {
  width: 14px;
  height: 10px;
  border: 2.5px solid var(--accentInk);
  border-bottom: none;
  border-radius: 8px 8px 0 0;
}
.lock b {
  width: 22px;
  height: 16px;
  border-radius: 4px;
  background: var(--accentInk);
}
.privacy-title {
  margin: 0;
  font: 500 28px/1.1 var(--serif);
}
.privacy-text {
  margin: 0;
  font: 400 14px/1.55 var(--sans);
  text-wrap: pretty;
}
.privacy-fine {
  margin: 0;
  font: 400 13px/1.5 var(--sans);
  color: var(--muted);
}

/* Install */
.install {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.install-title {
  margin: 0;
  font: 500 30px/1.1 var(--serif);
}
.steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.step {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border-radius: 20px;
  background: var(--surface);
}
.step-num {
  width: 30px;
  height: 30px;
  border-radius: 15px;
  background: var(--accent);
  color: var(--onAccent);
  display: grid;
  place-items: center;
  font: 700 14px/1 var(--sans);
  flex: none;
}
.step-text {
  flex: 1;
  font: 500 15px/1.35 var(--sans);
}
.art {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--surface2);
  display: grid;
  place-items: center;
  flex: none;
  color: var(--accentInk);
  font: 700 16px/1 var(--sans);
}
.art.dots {
  font-size: 14px;
  letter-spacing: 1px;
}
.art.menu {
  font-size: 22px;
}
.art img {
  width: 40px;
  height: 40px;
  border-radius: 10px;
}
/* The iOS share glyph: a box with an arrow out of the top. */
.share-box {
  position: relative;
  width: 16px;
  height: 18px;
  margin-top: 6px;
  border: 2px solid var(--accentInk);
  border-top: none;
  border-radius: 0 0 3px 3px;
}
.share-box::before {
  content: '';
  position: absolute;
  left: 50%;
  top: -12px;
  width: 2px;
  height: 14px;
  margin-left: -1px;
  background: var(--accentInk);
}
.share-box::after {
  content: '';
  position: absolute;
  left: 50%;
  top: -12px;
  width: 7px;
  height: 7px;
  margin-left: -3.5px;
  border-left: 2px solid var(--accentInk);
  border-top: 2px solid var(--accentInk);
  transform: rotate(45deg);
}
.fine {
  margin: 0;
  font: 400 13px/1.5 var(--sans);
  color: var(--muted);
  text-wrap: pretty;
}
.fine.small {
  font-size: 12px;
  text-align: center;
}
.foot {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 20px;
  border-top: 1px solid var(--line);
}
.foot .btn {
  height: 48px;
  font-size: 14px;
}

/* Android install bar */
.android-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 16px 20px max(30px, calc(var(--safe-bottom) + 12px));
  background: var(--surface);
  border-top: 1px solid var(--line);
  z-index: 19;
}

/* Pointer toward the real Safari controls */
.pointer {
  position: fixed;
  z-index: 20;
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: none;
  animation: bounce 1.4s ease-in-out infinite;
}
.pointer.bottom {
  left: 50%;
  bottom: calc(14px + var(--safe-bottom));
  transform: translateX(-50%);
}
.pointer.bottom-right {
  right: 12px;
  bottom: calc(14px + var(--safe-bottom));
  align-items: flex-end;
}
.pointer.bottom-right .tip-arrow {
  margin-right: 14px;
}
.pointer.top {
  right: 16px;
  top: calc(10px + var(--safe-top));
  align-items: flex-end;
  animation-name: bounceUp;
}
.tip {
  padding: 10px 14px;
  border-radius: 14px;
  background: var(--accent);
  color: var(--onAccent);
  font: 600 13px/1.2 var(--sans);
  white-space: nowrap;
  box-shadow: 0 10px 24px -10px rgb(0 0 0 / 0.5);
}
.tip-arrow {
  width: 0;
  height: 0;
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
  border-top: 9px solid var(--accent);
}
.tip-arrow.up {
  border-top: none;
  border-bottom: 9px solid var(--accent);
  margin-right: 14px;
}

/* In-app browser */
.inapp {
  position: relative;
  min-height: 100dvh;
  max-width: 480px;
  margin: 0 auto;
  padding: max(70px, calc(var(--safe-top) + 50px)) 26px max(48px, calc(var(--safe-bottom) + 16px));
  display: flex;
  flex-direction: column;
  gap: 22px;
  animation: fadeIn 0.6s ease both;
}
.up-hint {
  position: absolute;
  top: max(10px, var(--safe-top));
  right: 22px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  color: var(--accentInk);
  font: 600 12px/1 var(--sans);
  animation: bounceUp 1.4s ease-in-out infinite;
}
.up-hint span:first-child {
  font-size: 22px;
}
.inapp-mid {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 18px;
}

@keyframes bounce {
  0%, 100% { translate: 0 0; }
  50% { translate: 0 6px; }
}
@keyframes bounceUp {
  0%, 100% { translate: 0 0; }
  50% { translate: 0 -6px; }
}
</style>
