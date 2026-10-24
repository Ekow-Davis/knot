<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuth } from '@/stores/auth'

const router = useRouter()
const auth = useAuth()

function again() {
  auth.resetFlow()
  router.replace({ name: 'email' })
}
</script>

<template>
  <main class="screen">
    <div class="grow away">
      <h1 class="title">You've been away a while.</h1>
      <p class="sub">For safety we signed you out. Sign in again and you'll pick up where you left off.</p>
    </div>
    <button class="btn" type="button" @click="again">Sign in again</button>
  </main>
</template>

<style scoped>
.away {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 12px;
}
</style>
