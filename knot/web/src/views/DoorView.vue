<script setup lang="ts">
/**
 * The door: first screen of the installed app.
 * Session 1 placeholder — proves the shell, theme and API connection work end to end.
 * Session 2 replaces the body with the email → code → pairing → name flow.
 */
import { onMounted, ref } from 'vue'
import KnotMark from '@/components/KnotMark.vue'
import { api } from '@/lib/api'

const status = ref<'checking' | 'ok' | 'down'>('checking')

onMounted(async () => {
  try {
    await api.get<{ ok: boolean }>('/health')
    status.value = 'ok'
  } catch {
    status.value = 'down'
  }
})
</script>

<template>
  <main class="door">
    <KnotMark :size="84" />
    <h1 class="serif">Knot</h1>
    <p class="sub">Two people. One question at a time.</p>

    <p class="status" :data-status="status" role="status">
      <span class="dot" />
      {{ status === 'checking' ? 'Reaching the server…' : status === 'ok' ? 'Connected' : 'Server unreachable' }}
    </p>
  </main>
</template>

<style scoped>
.door {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 24px;
  text-align: center;
  background: radial-gradient(ellipse at 50% 30%, var(--surface) 0%, var(--bg) 60%, var(--bg2) 100%);
}
h1 {
  margin: 16px 0 0;
  font-size: 56px;
  font-weight: 500;
  letter-spacing: 0.01em;
}
.sub {
  margin: 0;
  color: var(--muted);
}
.status {
  margin-top: 40px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--muted);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--line);
}
[data-status='ok'] .dot {
  background: var(--accent);
  box-shadow: 0 0 10px var(--glow);
}
[data-status='down'] .dot {
  background: var(--warn);
}
</style>
