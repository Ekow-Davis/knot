<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import BackButton from '@/components/BackButton.vue'
import CodeBoxes from '@/components/CodeBoxes.vue'
import { ApiError } from '@/lib/api'
import { toast } from '@/lib/toast'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const router = useRouter()

const code = ref('')
const busy = ref(false)
const err = ref<'wrong' | 'expired' | 'other' | null>(null)
const otherMessage = ref('')
const shake = ref(0)
const boxes = ref<InstanceType<typeof CodeBoxes> | null>(null)

// Resend countdown.
const resendIn = ref(auth.flow.resendAfter)
let tick: ReturnType<typeof setInterval> | undefined
function startCountdown(seconds: number) {
  resendIn.value = seconds
  clearInterval(tick)
  tick = setInterval(() => {
    resendIn.value = Math.max(0, resendIn.value - 1)
    if (resendIn.value === 0) clearInterval(tick)
  }, 1000)
}
onMounted(() => startCountdown(auth.flow.resendAfter))
onBeforeUnmount(() => clearInterval(tick))

const resendLabel = computed(() => {
  if (resendIn.value <= 0) return 'Resend code'
  const m = Math.floor(resendIn.value / 60)
  const s = String(resendIn.value % 60).padStart(2, '0')
  return `Resend code in ${m}:${s}`
})

async function submit(value: string) {
  if (busy.value) return
  busy.value = true
  err.value = null
  try {
    const status = await auth.verify(value)
    if (status === 'signed_in') {
      toast(`Welcome back, ${auth.me?.display_name ?? 'you'}.`)
      router.replace({ name: 'home' })
    } else if (status === 'new_owner') {
      router.replace({ name: 'name' })
    } else {
      router.replace({ name: 'pair' })
    }
  } catch (e) {
    code.value = ''
    if (e instanceof ApiError && e.code === 'code_wrong') {
      err.value = 'wrong'
      shake.value++
    } else if (e instanceof ApiError && e.code === 'code_expired') {
      err.value = 'expired'
    } else {
      err.value = 'other'
      otherMessage.value =
        e instanceof ApiError && e.code === 'offline' ? 'No connection. Try again in a moment.' : (e as Error).message
    }
    boxes.value?.focus()
  } finally {
    busy.value = false
  }
}

async function resend() {
  if (resendIn.value > 0) return
  err.value = null
  code.value = ''
  try {
    await auth.requestCode(auth.flow.email)
    startCountdown(auth.flow.resendAfter)
    toast('A fresh code is on its way.')
  } catch (e) {
    err.value = 'other'
    otherMessage.value = (e as Error).message
  }
  boxes.value?.focus()
}
</script>

<template>
  <main class="screen">
    <BackButton :to="{ name: 'email' }" />
    <div class="heading">
      <h1 class="title">Check your inbox.</h1>
      <p class="sub">
        If {{ auth.flow.email || 'that address' }} is allowed in, a code is on its way. It's good for 10 minutes.
      </p>
    </div>

    <CodeBoxes ref="boxes" v-model="code" :error="!!err" :shake="shake" :disabled="busy" @complete="submit" />

    <p v-if="err === 'wrong'" class="error">That code doesn't match. Try the newest email.</p>
    <p v-else-if="err === 'expired'" class="error">That code has expired. Grab a fresh one below.</p>
    <p v-else-if="err === 'other'" class="error">{{ otherMessage }}</p>

    <button class="btn link" type="button" :disabled="resendIn > 0" @click="resend">{{ resendLabel }}</button>
    <div class="grow" />
    <p class="note">Paste works too. It fills in by itself.</p>
  </main>
</template>
