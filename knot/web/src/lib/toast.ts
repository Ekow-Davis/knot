/** One small message at the bottom of the screen at a time ("Welcome back, Ama."). */
import { ref } from 'vue'

export const toastMessage = ref<string | null>(null)
let timer: ReturnType<typeof setTimeout> | undefined

export function toast(message: string, ms = 2600) {
  toastMessage.value = message
  clearTimeout(timer)
  timer = setTimeout(() => (toastMessage.value = null), ms)
}
