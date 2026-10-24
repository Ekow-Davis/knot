<script setup lang="ts">
import { RouterView } from 'vue-router'
import { toastMessage } from '@/lib/toast'
</script>

<template>
  <RouterView v-slot="{ Component }">
    <Transition name="fade" mode="out-in">
      <component :is="Component" />
    </Transition>
  </RouterView>

  <Transition name="toast">
    <div v-if="toastMessage" class="toast" role="status" aria-live="polite">{{ toastMessage }}</div>
  </Transition>
</template>

<style>
.fade-enter-active,
.fade-leave-active {
  transition: opacity calc(0.35s * var(--m)) ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.toast {
  position: fixed;
  left: 50%;
  bottom: calc(28px + var(--safe-bottom));
  transform: translateX(-50%);
  max-width: calc(100vw - 48px);
  padding: 12px 18px;
  border-radius: 18px;
  background: var(--surface2);
  border: 1px solid var(--line);
  color: var(--ink);
  font: 500 14px/1.4 var(--sans);
  box-shadow: 0 12px 30px -12px rgb(0 0 0 / 0.5);
  z-index: 50;
}
.toast-enter-active,
.toast-leave-active {
  transition:
    opacity 0.3s,
    transform 0.3s;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, 10px);
}
</style>
