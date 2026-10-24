<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import BackButton from '@/components/BackButton.vue'
import { ApiError } from '@/lib/api'
import { toast } from '@/lib/toast'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const router = useRouter()

const code = ref('')
const busy = ref(false)
const error = ref<string | null>(null)
const full = ref(false)
const shake = ref(0)

const letters = computed(() => {
  const s = code.value.replace(/[^A-Z0-9]/gi, '')
  // Same rule as the server: only drop "TIE" when the full TIE-XXXXX was typed.
  return s.length === 8 && /^TIE/i.test(s) ? s.slice(3) : s
})
const ready = computed(() => letters.value.length >= 5)

function onInput(e: Event) {
  // Upper-case as she types; keep only letters, digits and the dash.
  code.value = (e.target as HTMLInputElement).value.toUpperCase().replace(/[^A-Z0-9-]/g, '')
  error.value = null
}

async function pair() {
  if (!ready.value || busy.value) return
  busy.value = true
  error.value = null
  try {
    await auth.checkInvite(code.value)
    router.push({ name: 'name' })
  } catch (e) {
    const c = e instanceof ApiError ? e.code : ''
    if (c === 'pair_full') full.value = true
    else if (c === 'ticket_expired') {
      toast(e instanceof ApiError ? e.message : 'Start again with your email.')
      auth.resetFlow()
      router.replace({ name: 'email' })
    } else {
      error.value =
        c === 'invite_invalid' || c === 'slow_down'
          ? (e as ApiError).message
          : c === 'offline'
            ? 'No connection. Try again in a moment.'
            : 'Something went wrong. Try again.'
      shake.value++
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="screen">
    <BackButton :to="{ name: 'email' }" />

    <template v-if="!full">
      <div class="heading">
        <span class="eyebrow">First time only</span>
        <h1 class="title">Enter the code you were given.</h1>
        <p class="sub">It pairs your phone with theirs. Once two people are paired, nobody else can join.</p>
      </div>
      <form @submit.prevent="pair">
        <input
          :key="shake"
          :value="code"
          class="field code"
          :class="{ shaking: shake }"
          placeholder="TIE-XXXXX"
          maxlength="12"
          autocapitalize="characters"
          autocomplete="off"
          autocorrect="off"
          spellcheck="false"
          enterkeyhint="go"
          aria-label="Pairing code"
          autofocus
          @input="onInput"
        />
      </form>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="grow" />
      <button class="btn" type="button" :disabled="!ready || busy" @click="pair">
        {{ busy ? 'Checking…' : 'Pair us' }}
      </button>
    </template>

    <template v-else>
      <div class="grow full">
        <div class="rings" aria-hidden="true">
          <span /><span /><span class="third" />
        </div>
        <h1 class="title full-title">This pair is already complete.</h1>
        <p class="sub full-sub">Knot only ever holds two people. If that seems wrong, ask whoever sent you the link.</p>
      </div>
      <button class="btn ghost" type="button" @click="router.replace({ name: 'door' })">Back to the door</button>
    </template>
  </main>
</template>

<style scoped>
.code {
  height: 64px;
  text-align: center;
  font: 600 24px/1 ui-monospace, Menlo, monospace;
  letter-spacing: 0.2em;
  text-transform: uppercase;
}
.shaking {
  animation: shake 0.45s ease;
}
.full {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 28px;
  text-align: center;
}
.full-title {
  font-size: 36px;
  line-height: 1.05;
}
.full-sub {
  max-width: 290px;
}
.rings {
  position: relative;
  width: 150px;
  height: 60px;
}
.rings span {
  position: absolute;
  top: 0;
  width: 60px;
  height: 60px;
  border-radius: 50%;
  border: 4px solid var(--accent);
}
.rings span:nth-child(1) {
  left: 10px;
}
.rings span:nth-child(2) {
  left: 46px;
}
.rings .third {
  left: 62px;
  border: 4px dashed var(--muted);
  animation: bumpOff 2.8s ease-in-out infinite;
}
</style>
