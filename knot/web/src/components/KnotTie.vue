<script setup lang="ts">
/**
 * The rope knot from the design (KnotTie): two strands that draw themselves, cross, then cinch.
 *   tie    → animates tying (door, and the moment the phrase is right)
 *   untie  → animates coming undone
 *   static → just the knot
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    w?: number
    mode?: 'tie' | 'untie' | 'static'
    delay?: number
    glow?: boolean
    strokeWidth?: number
    rope?: string
    twist?: string
    halo?: string
  }>(),
  {
    w: 200,
    mode: 'tie',
    delay: 0,
    glow: false,
    strokeWidth: 9,
    rope: 'var(--accent2)',
    twist: 'var(--accent)',
    halo: 'var(--bg)',
  },
)

const T = (s: number) => `calc(${s}s * var(--m, 1))`

const styles = computed(() => {
  const d = props.delay
  const sw = props.strokeWidth
  const base = { fill: 'none', strokeLinecap: 'round' as const, strokeWidth: sw, stroke: props.rope }
  const tw = (x: object) => ({ fill: 'none', stroke: props.twist, strokeWidth: sw, strokeDasharray: '1.6 2.4', ...x })
  const hb = { fill: 'none', stroke: props.halo, strokeWidth: sw + 7, strokeLinecap: 'round' as const }

  if (props.mode === 'static') {
    return { p1: base, p2: base, t: tw({}), halo: hb, svg: {} }
  }
  if (props.mode === 'untie') {
    return {
      p2: { ...base, strokeDasharray: 100, animation: `ropeUndo ${T(0.55)} ${T(d)} cubic-bezier(.5,0,.6,1) both` },
      p1: { ...base, strokeDasharray: 100, animation: `ropeUndo ${T(0.8)} ${T(d + 0.45)} cubic-bezier(.5,0,.6,1) both` },
      halo: { ...hb, animation: `fadeAway ${T(0.1)} ${T(d + 0.5)} both` },
      t: tw({ animation: `fadeAway ${T(0.2)} ${T(d)} both` }),
      svg: {},
    }
  }
  return {
    p1: { ...base, strokeDasharray: 100, animation: `ropeDraw ${T(1)} ${T(d)} cubic-bezier(.55,0,.25,1) both` },
    p2: { ...base, strokeDasharray: 100, animation: `ropeDraw ${T(0.7)} ${T(d + 0.85)} cubic-bezier(.55,0,.25,1) both` },
    halo: { ...hb, opacity: 0, animation: `fadeOnly ${T(0.1)} ${T(d + 0.9)} forwards` },
    t: tw({ opacity: 0, animation: `fadeOnly ${T(0.5)} ${T(d + 1.55)} forwards` }),
    svg: {
      transformOrigin: '50% 60%',
      animation: `cinch ${T(0.7)} ${T(d + 1.5)} ease both${props.glow ? `, glowLoop 3.2s ${T(d + 2.2)} ease-in-out infinite` : ''}`,
    },
  }
})

const A = 'M8,80 C45,80 72,82 94,66 C116,50 124,24 102,19 C80,14 68,38 80,56'
const B = 'M80,56 C90,72 104,80 124,80 C150,80 170,80 192,80'
</script>

<template>
  <svg
    :width="w"
    :height="Math.round(w * 0.6)"
    viewBox="0 0 200 120"
    fill="none"
    aria-hidden="true"
    :style="{ overflow: 'visible', display: 'block', ...styles.svg }"
  >
    <path :d="A" pathLength="100" :style="styles.p1" />
    <path :d="A" pathLength="100" :style="styles.t" />
    <path d="M84,62 C88,68 92,72 98,75" :style="styles.halo" />
    <path :d="B" pathLength="100" :style="styles.p2" />
    <path :d="B" pathLength="100" :style="styles.t" />
  </svg>
</template>

<style>
@keyframes ropeDraw {
  from { stroke-dashoffset: 100; }
  to { stroke-dashoffset: 0; }
}
@keyframes ropeUndo {
  from { stroke-dashoffset: 0; }
  to { stroke-dashoffset: 100; }
}
@keyframes fadeOnly {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes fadeAway {
  from { opacity: 1; }
  to { opacity: 0; }
}
@keyframes cinch {
  0% { transform: scale(1); }
  35% { transform: scale(1.08, 0.88); }
  100% { transform: scale(1); }
}
@keyframes glowLoop {
  0%, 100% { filter: drop-shadow(0 0 2px var(--glow)); }
  50% { filter: drop-shadow(0 0 12px var(--glow)); }
}
</style>
