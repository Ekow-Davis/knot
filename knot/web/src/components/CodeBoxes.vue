<script setup lang="ts">
/**
 * Six boxes over one invisible input. Using a single real input (not six) is what makes
 * iOS "From Messages/Mail" autofill and pasting work.
 */
import { computed, onMounted, ref } from 'vue'

const model = defineModel<string>({ required: true })
const props = defineProps<{ error?: boolean; shake?: number; disabled?: boolean }>()
const emit = defineEmits<{ complete: [code: string] }>()

const input = ref<HTMLInputElement | null>(null)

const boxes = computed(() =>
  Array.from({ length: 6 }, (_, i) => ({
    ch: model.value[i] ?? '',
    active: i === Math.min(model.value.length, 5) && model.value.length < 6,
  })),
)

function onInput(e: Event) {
  const v = (e.target as HTMLInputElement).value.replace(/\D/g, '').slice(0, 6)
  model.value = v
  ;(e.target as HTMLInputElement).value = v
  if (v.length === 6) emit('complete', v)
}

onMounted(() => input.value?.focus())
defineExpose({ focus: () => input.value?.focus() })
</script>

<template>
  <div class="wrap" @click="input?.focus()">
    <div :key="props.shake" class="row" :class="{ shaking: props.shake }">
      <div
        v-for="(b, i) in boxes"
        :key="i"
        class="box"
        :class="{ filled: b.ch, active: b.active && !props.error, error: props.error }"
      >
        {{ b.ch }}
      </div>
    </div>
    <input
      ref="input"
      :value="model"
      :disabled="props.disabled"
      inputmode="numeric"
      autocomplete="one-time-code"
      maxlength="6"
      aria-label="Six-digit code"
      @input="onInput"
    />
  </div>
</template>

<style scoped>
.wrap {
  position: relative;
}
.row {
  display: flex;
  gap: 8px;
  justify-content: center;
}
.row.shaking {
  animation: shake 0.45s ease;
}
.box {
  width: 46px;
  height: 58px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: var(--surface);
  border: 1px solid var(--line);
  font: 600 24px/1 var(--sans);
  transform: scale(0.97);
  transition:
    border-color 0.2s,
    transform 0.15s;
}
.box.filled {
  transform: none;
}
.box.active {
  border: 2px solid var(--accent);
}
.box.error {
  border: 1.5px solid var(--warn);
}
input {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  border: none;
  font-size: 16px;
  cursor: text;
  /* Hide the caret and iOS selection handles on the invisible input. */
  color: transparent;
  caret-color: transparent;
}
</style>
