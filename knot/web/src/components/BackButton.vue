<script setup lang="ts">
import { ChevronLeft } from 'lucide-vue-next'
import { useRouter, type RouteLocationRaw } from 'vue-router'

const props = defineProps<{ to: RouteLocationRaw }>()
const router = useRouter()
</script>

<template>
  <button class="back" type="button" aria-label="Back" @click="router.replace(props.to)">
    <ChevronLeft :size="22" :stroke-width="1.75" />
  </button>
</template>
