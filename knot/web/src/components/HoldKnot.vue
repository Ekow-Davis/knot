<script setup lang="ts">
/**
 * Press and hold to pull your end. Your half of the ring fills in your colour (1.2 seconds),
 * theirs fills in theirs as they hold. Once your half is full, your end stays pulled:
 * no need to keep holding while you wait for them.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps<{
  ready: boolean // everyone has sealed
  mine: string // my ring colour
  theirs: string // their ring colour
  partnerHolding: boolean
  partnerPulled: boolean
  iPulled: boolean
}>()
const emit = defineEmits<{ holding: [on: boolean]; pulled: [] }>()

const FILL_MS = 1200
const myHold = ref(props.iPulled ? 100 : 0)
const theirHold = ref(props.partnerPulled ? 100 : 0)
let myRaf = 0
let theirRaf = 0

function animate(from: number, to: number, set: (v: number) => void, done?: () => void) {
  const start = performance.now()
  const dur = Math.abs(to - from) * (FILL_MS / 100)
  const id = { v: 0 }
  const step = (t: number) => {
    const k = Math.min(1, (t - start) / Math.max(dur, 1))
    set(from + (to - from) * k)
    if (k < 1) id.v = requestAnimationFrame(step)
    else done?.()
  }
  id.v = requestAnimationFrame(step)
  return () => cancelAnimationFrame(id.v)
}

let stopMine: (() => void) | null = null
function press(e: PointerEvent) {
  if (!props.ready || props.iPulled) return
  ;(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId)
  emit('holding', true)
  stopMine?.()
  stopMine = animate(myHold.value, 100, (v) => (myHold.value = v), () => emit('pulled'))
}
function release() {
  if (props.iPulled || myHold.value >= 100) return
  emit('holding', false)
  stopMine?.()
  stopMine = animate(myHold.value, 0, (v) => (myHold.value = v))
}

let stopTheirs: (() => void) | null = null
watch(
  () => [props.partnerHolding, props.partnerPulled] as const,
  ([holding, pulled]) => {
    stopTheirs?.()
    if (pulled) stopTheirs = animate(theirHold.value, 100, (v) => (theirHold.value = v))
    else stopTheirs = animate(theirHold.value, holding ? 100 : 0, (v) => (theirHold.value = v))
  },
)
watch(
  () => props.iPulled,
  (p) => {
    if (p && myHold.value < 100) stopMine = animate(myHold.value, 100, (v) => (myHold.value = v))
  },
)

onBeforeUnmount(() => {
  stopMine?.()
  stopTheirs?.()
  cancelAnimationFrame(myRaf)
  cancelAnimationFrame(theirRaf)
})

// Ring: their half fills clockwise from the top on the right, yours anticlockwise on the left.
const ring = computed(() => {
  const th = theirHold.value * 1.8
  const mh = 360 - myHold.value * 1.8
  return `conic-gradient(${props.theirs} 0deg ${th}deg, var(--line) ${th}deg 180deg, var(--line) 180deg ${mh}deg, ${props.mine} ${mh}deg 360deg)`
})
const pull = computed(() => (myHold.value + theirHold.value) / 500)
const myRing = computed(() => ({ borderColor: props.mine, transform: `translateX(${-myHold.value / 7}px)` }))
const theirRing = computed(() => ({ borderColor: props.theirs, transform: `translateX(${theirHold.value / 7}px)` }))
</script>

<template>
  <div
    class="hold"
    :class="{ ready, pulsing: ready && myHold === 0 }"
    role="button"
    :aria-label="iPulled ? 'Your end is pulled' : 'Press and hold to pull your end'"
    :aria-disabled="!ready || iPulled"
    tabindex="0"
    @pointerdown="press"
    @pointerup="release"
    @pointerleave="release"
    @pointercancel="release"
    @keydown.space.prevent="emit('pulled')"
    @keydown.enter.prevent="emit('pulled')"
    @contextmenu.prevent
  >
    <div class="ring" :style="{ background: ring }" />
    <div class="inner">
      <div class="knot" :style="{ transform: `scale(${1 + pull})` }">
        <span class="r left" :style="myRing" />
        <span class="r right" :style="theirRing" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.hold {
  position: relative;
  width: 196px;
  height: 196px;
  border-radius: 50%;
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
  cursor: pointer;
}
.ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  opacity: 0.5;
  transition: opacity 0.3s;
}
.ready .ring {
  opacity: 1;
}
.pulsing .ring {
  animation: ringPulse 1.6s ease-out infinite;
}
.inner {
  position: absolute;
  inset: 9px;
  border-radius: 50%;
  background: radial-gradient(circle at 50% 40%, var(--surface2), var(--surface));
  display: grid;
  place-items: center;
}
.knot {
  position: relative;
  width: 96px;
  height: 58px;
  opacity: 0.55;
  animation: breathe 3s ease-in-out infinite;
}
.ready .knot {
  opacity: 1;
  filter: drop-shadow(0 0 10px var(--glow));
  animation: none;
}
.r {
  position: absolute;
  top: 0;
  width: 58px;
  height: 58px;
  border-radius: 50%;
  border: 4px solid;
  transition: transform 0.1s;
}
.r.left {
  left: 0;
}
.r.right {
  right: 0;
}
@keyframes ringPulse {
  0% { box-shadow: 0 0 0 0 var(--glow); }
  100% { box-shadow: 0 0 0 22px transparent; }
}
@keyframes breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}
</style>
