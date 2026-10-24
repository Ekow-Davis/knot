<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import BackButton from '@/components/BackButton.vue'
import { ApiError } from '@/lib/api'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const router = useRouter()

const email = ref(auth.flow.email)
const busy = ref(false)
const error = ref<string | null>(null)
const looksValid = computed(() => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim()))

async function send() {
  if (!looksValid.value || busy.value) return
  busy.value = true
  error.value = null
  try {
    await auth.requestCode(email.value)
    router.push({ name: 'code' })
  } catch (e) {
    error.value =
      e instanceof ApiError && e.code === 'offline'
        ? 'No connection. Check your internet and try again.'
        : e instanceof ApiError && e.code === 'slow_down'
          ? e.message
          : 'That email doesn’t look quite right.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="screen">
    <BackButton :to="{ name: 'door' }" />
    <div class="heading">
      <h1 class="title">What's your email?</h1>
      <p class="sub">We'll send a six-digit code. No passwords to remember.</p>
    </div>
    <form @submit.prevent="send">
      <input
        v-model="email"
        class="field"
        type="email"
        inputmode="email"
        autocomplete="email"
        autocapitalize="off"
        spellcheck="false"
        placeholder="you@example.com"
        enterkeyhint="send"
        autofocus
      />
    </form>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="grow" />
    <div class="actions">
      <button class="btn" type="button" :disabled="!looksValid || busy" @click="send">
        {{ busy ? 'Sending…' : 'Send me a code' }}
      </button>
      <p class="note">For privacy, we never say whether an email is allowed in.</p>
    </div>
  </main>
</template>

<style scoped>
.actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>
