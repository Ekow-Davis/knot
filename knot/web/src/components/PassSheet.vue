<script setup lang="ts">
/** iOS-style bottom sheet for passing. Swipe it down (or tap outside) to keep the question. */
import { ref } from 'vue'
import { useSwipe } from '@/lib/swipe'

defineProps<{ partner: string }>()
const emit = defineEmits<{ pass: []; retire: []; close: [] }>()

const sheet = ref<HTMLElement | null>(null)
useSwipe(sheet, { down: () => emit('close') })
</script>

<template>
  <div class="backdrop" @click.self="emit('close')">
    <div ref="sheet" class="sheet" role="dialog" aria-label="Pass on this question">
      <span class="grabber" aria-hidden="true" />
      <p class="lead">No reason needed. Anything already sealed is let go, unread.</p>
      <button class="btn" type="button" @click="emit('pass')">Pass on this one</button>
      <button class="btn ghost" type="button" @click="emit('retire')">Never show this one again</button>
      <p class="fine">Takes it out of the deck for both of you, for good.</p>
      <button class="btn link" type="button" @click="emit('close')">Keep it</button>
    </div>
  </div>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: rgb(0 0 0 / 0.45);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  animation: fadeOnly 0.2s ease both;
}
.sheet {
  width: 100%;
  max-width: 480px;
  padding: 10px 22px max(22px, calc(var(--safe-bottom) + 12px));
  border-radius: 28px 28px 0 0;
  background: var(--surface);
  border-top: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 10px;
  animation: sheetUp 0.32s cubic-bezier(0.2, 0.9, 0.3, 1) both;
  touch-action: pan-x;
}
.grabber {
  align-self: center;
  width: 38px;
  height: 5px;
  border-radius: 3px;
  background: var(--line);
  margin-bottom: 8px;
}
.lead {
  margin: 0 0 6px;
  text-align: center;
  font: 400 14px/1.45 var(--sans);
  color: var(--muted);
}
.fine {
  margin: -4px 0 0;
  text-align: center;
  font: 400 12px/1.4 var(--sans);
  color: var(--muted);
}
@keyframes sheetUp {
  from { transform: translateY(100%); }
  to { transform: none; }
}
@keyframes fadeOnly {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
