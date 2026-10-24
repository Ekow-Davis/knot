<script setup lang="ts">
/** "Can we tug your sleeve?" Shown once, after the knot is tied, on a phone that supports it. */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { enablePush, markAskedForPush } from '@/lib/push'
import { toast } from '@/lib/toast'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const router = useRouter()
const P = auth.partnerName
const busy = ref(false)

async function allow() {
  busy.value = true
  markAskedForPush()
  try {
    const state = await enablePush()
    if (state === 'on') toast(`Tugs on. Only ever from ${P}.`)
    else if (state === 'denied') toast('No problem. You can turn them on later in Settings.')
  } catch {
    toast('That didn’t work. You can try again in Settings.')
  } finally {
    busy.value = false
    router.replace({ name: 'home' })
  }
}

function skip() {
  markAskedForPush()
  router.replace({ name: 'home' })
}
</script>

<template>
  <main class="screen notify">
    <div class="heading top">
      <h1 class="title">Can we tug your sleeve?</h1>
      <p class="sub">Only for two things. Never streaks, never “we miss you”.</p>
    </div>

    <div class="fakes" aria-hidden="true">
      <div class="fake one">
        <img src="/icons/icon-192.png" alt="" />
        <div>
          <span class="app">W.W. · NOW</span>
          <span class="msg">{{ P }} gave the rope a little tug.</span>
        </div>
      </div>
      <div class="fake two">
        <img src="/icons/icon-192.png" alt="" />
        <div>
          <span class="app">W.W. · 2M AGO</span>
          <span class="msg">{{ P }} left you a sealed question.</span>
        </div>
      </div>
    </div>

    <p class="sub small">Notifications never include the question or anyone's answer.</p>
    <div class="grow" />
    <div class="actions">
      <button class="btn" type="button" :disabled="busy" @click="allow">Allow tugs</button>
      <button class="btn link muted" type="button" @click="skip">Not now</button>
    </div>
  </main>
</template>

<style scoped>
.notify {
  gap: 26px;
}
.top {
  padding-top: 30px;
}
.fakes {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.fake {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border-radius: 22px;
  background: var(--surface);
  animation: pushIn 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.1) both;
}
.fake.one {
  animation-delay: 0.3s;
}
.fake.two {
  animation-delay: 0.7s;
}
.fake img {
  width: 38px;
  height: 38px;
  border-radius: 9px;
  flex: none;
}
.fake div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.app {
  font: 700 11px/1 var(--sans);
  letter-spacing: 0.08em;
  color: var(--muted);
}
.msg {
  font: 500 14px/1.3 var(--sans);
}
.small {
  font-size: 13px;
}
.actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.muted {
  color: var(--muted);
  font-weight: 500;
  font-size: 15px;
}
@keyframes pushIn {
  from { opacity: 0; transform: translateY(-130%); }
  to { opacity: 1; transform: none; }
}
</style>
