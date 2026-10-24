<script setup lang="ts">
/** The door: first screen of the installed app for anyone not signed in. */
import { useRouter } from 'vue-router'
import KnotTie from '@/components/KnotTie.vue'

const router = useRouter()
</script>

<template>
  <main class="screen door">
    <div class="grow stage">
      <div class="arch" aria-hidden="true">
        <div class="inner" />
        <div class="seam" />
        <div class="knot"><KnotTie :w="238" mode="tie" :delay="0.4" glow halo="var(--surface2)" /></div>
        <div class="keyhole"><span /><span /></div>
      </div>
      <div class="words">
        <h1 class="name">Knot</h1>
        <p class="sub">This door only opens for two. If that isn't you, it was lovely to meet you anyway.</p>
      </div>
    </div>
    <button class="btn" type="button" @click="router.push({ name: 'email' })">Come in</button>
  </main>
</template>

<style scoped>
.door {
  padding-top: max(80px, calc(var(--safe-top) + 30px));
  align-items: center;
  animation-duration: calc(0.9s * var(--m));
}
.stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 36px;
  width: 100%;
}
.arch {
  position: relative;
  width: 210px;
  height: 300px;
  border-radius: 105px 105px 8px 8px;
  background: var(--surface2);
  box-shadow:
    inset 0 0 0 1px var(--line),
    0 40px 90px -30px var(--glow);
}
.inner {
  position: absolute;
  inset: 14px 14px 0;
  border-radius: 91px 91px 2px 2px;
  border: 1px solid var(--line);
  border-bottom: none;
}
.seam {
  position: absolute;
  left: 104px;
  top: 40px;
  bottom: 0;
  width: 1px;
  background: var(--line);
}
.knot {
  position: absolute;
  left: -14px;
  top: 100px;
}
.keyhole {
  position: absolute;
  left: 50%;
  bottom: 44px;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
}
.keyhole span:first-child {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--bg2);
}
.keyhole span:last-child {
  width: 6px;
  height: 14px;
  margin-top: -3px;
  background: var(--bg2);
  border-radius: 0 0 2px 2px;
}
.words {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  text-align: center;
}
.name {
  margin: 0;
  font: italic 500 48px/1 var(--serif);
  color: var(--accentInk);
}
.sub {
  max-width: 260px;
  font-size: 15px;
  line-height: 1.55;
}
</style>
