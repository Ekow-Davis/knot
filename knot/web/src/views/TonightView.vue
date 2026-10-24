<script setup lang="ts">
/** "That's enough for tonight." The count lives on this phone for the evening only. */
import { useRouter } from 'vue-router'
import KnotTie from '@/components/KnotTie.vue'
import { knotsTied } from '@/lib/words'
import { useRound } from '@/stores/round'

const router = useRouter()
const n = useRound().endTonight()
</script>

<template>
  <main class="screen tonight">
    <div class="grow mid">
      <KnotTie :w="140" mode="tie" :delay="0.3" glow />
      <h1 class="title big">{{ n > 0 ? knotsTied(n) : 'Not tonight, then.' }}</h1>
    </div>
    <button class="btn" type="button" @click="router.replace({ name: 'home' })">Back home</button>
  </main>
</template>

<style scoped>
.mid {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 28px;
  text-align: center;
}
.big {
  font-size: 40px;
  line-height: 1.05;
  animation: fadeIn calc(1s * var(--m)) calc(1.8s * var(--m)) ease both;
}
</style>
