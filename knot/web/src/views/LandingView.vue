<script setup lang="ts">
/**
 * Landing page: shown when the link is opened in a browser rather than from the home screen.
 * Session 1 placeholder — detects the browser so Session 6 can show the right install steps.
 */
import KnotMark from '@/components/KnotMark.vue'
import { detectBrowser } from '@/lib/platform'

const browser = detectBrowser()

const hint: Record<typeof browser, string> = {
  safari: 'Tap Share, then “Add to Home Screen”.',
  inapp: 'Open this link in Safari first. This browser can’t install it.',
  android: 'Tap Install when your browser offers it.',
  desktop: 'Open this on your phone to install it.',
}
</script>

<template>
  <main class="landing">
    <KnotMark :size="64" />
    <h1 class="serif">Knot</h1>
    <p class="lede">A question game for two. Answer in secret, reveal together, and then it’s gone.</p>
    <p class="hint">{{ hint[browser] }}</p>
  </main>
</template>

<style scoped>
.landing {
  min-height: 100dvh;
  max-width: 440px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 24px 16px;
  text-align: center;
}
h1 {
  margin: 12px 0 0;
  font-size: 48px;
  font-weight: 500;
}
.lede {
  margin: 0;
  color: var(--muted);
  text-wrap: pretty;
}
.hint {
  margin-top: 28px;
  padding: 14px 18px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: var(--surface);
  font-size: 14px;
}
</style>
