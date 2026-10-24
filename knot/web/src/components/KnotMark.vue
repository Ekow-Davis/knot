<script setup lang="ts">
/** Two interlocking rings: the Knot mark used on the door and landing page. */
withDefaults(defineProps<{ size?: number }>(), { size: 84 })
</script>

<template>
  <svg :width="size * 1.6" :height="size" viewBox="0 0 136 84" aria-hidden="true" class="mark">
    <circle cx="42" cy="42" r="34" fill="none" stroke="var(--accent)" stroke-width="6" />
    <circle cx="94" cy="42" r="34" fill="none" stroke="var(--accent2)" stroke-width="6" />
    <!-- Redraw the first ring over the top crossing only; the second ring stays on top at the
         bottom crossing, so they read as interlocked. -->
    <path d="M 59 12.56 A 34 34 0 0 1 76 42" fill="none" stroke="var(--accent)" stroke-width="6" />
  </svg>
</template>

<style scoped>
.mark {
  filter: drop-shadow(0 0 18px var(--glow));
}
</style>
