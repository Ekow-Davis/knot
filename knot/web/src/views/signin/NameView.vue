<script setup lang="ts">
/** Last first-time step: what the other person sees you as. Not in the original design;
 *  built in the same style as the other sign-in screens. */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import BackButton from '@/components/BackButton.vue'
import { ApiError } from '@/lib/api'
import { toast } from '@/lib/toast'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const router = useRouter()

const name = ref('')
const busy = ref(false)
const error = ref<string | null>(null)
const ready = computed(() => name.value.trim().length > 0)
const isOwner = auth.flow.kind === 'new_owner'

async function finish() {
  if (!ready.value || busy.value) return
  busy.value = true
  error.value = null
  try {
    await auth.join(name.value.trim())
    toast(isOwner ? 'You’re in. Make a pairing code when you’re ready.' : `You’re paired with ${auth.partnerName}.`)
    router.replace({ name: 'home' })
  } catch (e) {
    const c = e instanceof ApiError ? e.code : ''
    if (c === 'invite_invalid' || c === 'pair_full') {
      // The code stopped working between steps (used, cancelled or expired).
      toast((e as ApiError).message)
      router.replace({ name: 'pair' })
    } else if (c === 'ticket_expired') {
      toast((e as ApiError).message)
      auth.resetFlow()
      router.replace({ name: 'email' })
    } else {
      error.value = c === 'offline' ? 'No connection. Try again in a moment.' : 'Something went wrong. Try again.'
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="screen">
    <BackButton :to="{ name: isOwner ? 'email' : 'pair' }" />
    <div class="heading">
      <span class="eyebrow">Last thing</span>
      <h1 class="title">What should they call you?</h1>
      <p class="sub">A first name or a nickname, whatever feels like you. You can change it later.</p>
    </div>
    <form @submit.prevent="finish">
      <input
        v-model="name"
        class="field"
        maxlength="40"
        autocomplete="nickname"
        autocapitalize="words"
        enterkeyhint="done"
        placeholder="Your name"
        aria-label="Your name"
        autofocus
      />
    </form>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="grow" />
    <button class="btn" type="button" :disabled="!ready || busy" @click="finish">
      {{ busy ? 'One moment…' : 'That’s me' }}
    </button>
  </main>
</template>
