/**
 * Swipe gestures for touch (and mouse drags, for testing on a laptop).
 *
 *   useSwipe(elRef, { left, right, up, down })
 *
 * A swipe counts when the finger travels at least 60px mostly in one direction within 600ms.
 * Taps, scrolls and slow drags are left alone, and swipes that start in a text field are
 * ignored so selecting text never triggers anything. Works for elements that come and go
 * (v-if): it re-attaches whenever the ref points at a new element.
 */
import { onBeforeUnmount, watch, type Ref } from 'vue'

type Dir = 'left' | 'right' | 'up' | 'down'
export type SwipeHandlers = Partial<Record<Dir, () => void>>

const MIN_DISTANCE = 60
const MAX_TIME = 600

export function useSwipe(target: Ref<HTMLElement | null | undefined>, handlers: SwipeHandlers) {
  let x0 = 0
  let y0 = 0
  let t0 = 0
  let active = false

  function down(e: PointerEvent) {
    const el = e.target as HTMLElement
    if (el.closest('input, textarea, [contenteditable], [data-no-swipe]')) return
    if (e.pointerType === 'mouse' && e.button !== 0) return
    x0 = e.clientX
    y0 = e.clientY
    t0 = performance.now()
    active = true
  }

  function up(e: PointerEvent) {
    if (!active) return
    active = false
    const dx = e.clientX - x0
    const dy = e.clientY - y0
    if (performance.now() - t0 > MAX_TIME) return
    const ax = Math.abs(dx)
    const ay = Math.abs(dy)
    if (Math.max(ax, ay) < MIN_DISTANCE) return
    // Must be clearly one direction: 1.5× more along one axis than the other.
    let dir: Dir | null = null
    if (ax > ay * 1.5) dir = dx > 0 ? 'right' : 'left'
    else if (ay > ax * 1.5) dir = dy > 0 ? 'down' : 'up'
    if (dir) handlers[dir]?.()
  }

  function cancel() {
    active = false
  }

  function attach(el: HTMLElement) {
    el.addEventListener('pointerdown', down, { passive: true })
    el.addEventListener('pointerup', up, { passive: true })
    el.addEventListener('pointercancel', cancel, { passive: true })
  }
  function detach(el: HTMLElement) {
    el.removeEventListener('pointerdown', down)
    el.removeEventListener('pointerup', up)
    el.removeEventListener('pointercancel', cancel)
  }

  const stop = watch(
    target,
    (el, old) => {
      if (old) detach(old)
      if (el) attach(el)
    },
    { immediate: true, flush: 'post' },
  )
  onBeforeUnmount(() => {
    stop()
    if (target.value) detach(target.value)
  })
}
