<script setup lang="ts">
/**
 * A retícula — o cursor do projeto.
 *
 * Uma cruz magenta, e só. Ela fica exatamente sob o ponteiro, sem atraso
 * nenhum: substituir o cursor do sistema não pode custar precisão, que é
 * justamente o que um cursor faz. O que reage é a própria cruz — cresce e
 * engrossa sobre qualquer coisa clicável — em vez de um segundo elemento
 * perseguindo atrás.
 *
 * Só monta onde existe mouse (`pointer: fine`) e fora de movimento reduzido.
 * Em toque, o cursor nativo é o certo e este componente nem entra no DOM.
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { gsap } from 'gsap'

const cross = ref<HTMLElement | null>(null)
const active = ref(false)

const INTERACTIVE = 'a, button, [role="button"], [data-region], input, select, textarea'

function onMove(event: PointerEvent) {
  if (event.pointerType === 'touch') return
  gsap.set(cross.value, { x: event.clientX, y: event.clientY })
}

function onOver(event: PointerEvent) {
  active.value = Boolean((event.target as Element | null)?.closest?.(INTERACTIVE))
}

onMounted(() => {
  document.documentElement.classList.add('has-reticle')
  window.addEventListener('pointermove', onMove, { passive: true })
  window.addEventListener('pointerover', onOver, { passive: true })
})

onBeforeUnmount(() => {
  document.documentElement.classList.remove('has-reticle')
  window.removeEventListener('pointermove', onMove)
  window.removeEventListener('pointerover', onOver)
})
</script>

<template>
  <div class="pointer-events-none fixed inset-0 z-[100]" aria-hidden="true">
    <div ref="cross" class="absolute left-0 top-0">
      <span
        class="absolute block -translate-x-1/2 -translate-y-1/2 bg-accent
               transition-[width,height] duration-200 ease-out"
        :class="active ? 'h-[3px] w-8' : 'h-[3px] w-6'"
      />
      <span
        class="absolute block -translate-x-1/2 -translate-y-1/2 bg-accent
               transition-[width,height] duration-200 ease-out"
        :class="active ? 'h-8 w-[3px]' : 'h-6 w-[3px]'"
      />
    </div>
  </div>
</template>
