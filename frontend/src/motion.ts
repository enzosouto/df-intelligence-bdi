/**
 * Motion do DF Intelligence, em GSAP.
 *
 * Uma ideia só, aplicada em toda parte: **a página é plotada, não desenhada de
 * uma vez.** As réguas da grade crescem a partir da margem esquerda, depois o
 * conteúdo assenta em cima delas, e por último os números correm até o valor.
 * É a ordem em que um desenho técnico nasce — e é a mesma ordem em que o dado
 * chega: fonte, tabela, número.
 *
 * Elementos montados no mesmo quadro formam um grupo e entram em cascata
 * juntos; o grupo só toca quando encosta na viewport, então a página inteira
 * não gasta a sua animação de entrada acima da dobra.
 */
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import type { Directive } from 'vue'

gsap.registerPlugin(ScrollTrigger)

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

export function hasFinePointer(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(pointer: fine)').matches
}

/** Curva única do projeto: sai rápido, assenta devagar. Sem bounce. */
export const EASE = 'power3.out'

/* -------------------------------------------------------------------------- */
/* Ponteiro                                                                    */
/* -------------------------------------------------------------------------- */

/**
 * Posição do cursor em coordenadas de viewport.
 *
 * É um objeto simples, de propósito: o fundo em canvas e a retícula leem isto
 * a cada quadro, e passar por reatividade do Vue custaria um disparo de
 * dependência por movimento de mouse sem ganho nenhum.
 */
export const pointer = { x: -1000, y: -1000, active: false }

let pointerBound = false

export function bindPointer(): void {
  if (pointerBound || typeof window === 'undefined') return
  pointerBound = true
  window.addEventListener(
    'pointermove',
    (event) => {
      if (event.pointerType === 'touch') return
      pointer.x = event.clientX
      pointer.y = event.clientY
      pointer.active = true
    },
    { passive: true },
  )
  window.addEventListener('pointerleave', () => {
    pointer.active = false
  })
}

/* -------------------------------------------------------------------------- */
/* Revelação                                                                   */
/* -------------------------------------------------------------------------- */

type Pending = { el: HTMLElement; kind: 'block' | 'rule' }

let pending: Pending[] = []
let scheduled = false

function flush() {
  scheduled = false
  const batch = pending
  pending = []
  if (batch.length === 0) return

  const rules = batch.filter((item) => item.kind === 'rule').map((item) => item.el)
  const blocks = batch.filter((item) => item.kind === 'block').map((item) => item.el)
  const anchor = batch[0].el

  const timeline = gsap.timeline({
    paused: true,
    defaults: { ease: EASE },
  })

  if (rules.length) {
    timeline.to(rules, {
      scaleX: 1,
      duration: 0.5,
      stagger: { each: 0.04, from: 'start' },
    })
  }

  if (blocks.length) {
    timeline.to(
      blocks,
      {
        opacity: 1,
        y: 0,
        duration: 0.55,
        stagger: { each: 0.055, from: 'start' },
        clearProps: 'transform',
      },
      rules.length ? '-=0.35' : 0,
    )
  }

  // `once` porque re-animar no scroll de volta vira enfeite: a entrada existe
  // para apresentar o conteúdo, e ele só é apresentado uma vez.
  ScrollTrigger.create({
    trigger: anchor,
    start: 'top 92%',
    once: true,
    onEnter: () => timeline.play(),
  })
}

function enqueue(el: HTMLElement, kind: Pending['kind']) {
  pending.push({ el, kind })
  if (!scheduled) {
    scheduled = true
    requestAnimationFrame(flush)
  }
}

/**
 * `v-reveal` — entra em cascata com os irmãos montados no mesmo quadro.
 * `v-reveal.rule` — régua que é plotada da esquerda para a direita.
 */
export const reveal: Directive<HTMLElement> = {
  mounted(el, binding) {
    const kind = binding.modifiers.rule ? 'rule' : 'block'
    if (prefersReducedMotion()) return

    if (kind === 'rule') {
      gsap.set(el, { scaleX: 0, transformOrigin: 'left center' })
    } else {
      gsap.set(el, { opacity: 0, y: 14 })
    }
    enqueue(el, kind)
  },
  unmounted(el) {
    gsap.killTweensOf(el)
    pending = pending.filter((item) => item.el !== el)
  },
}

/* -------------------------------------------------------------------------- */
/* Reação ao cursor                                                            */
/* -------------------------------------------------------------------------- */

/**
 * O painel acende onde o cursor está.
 *
 * Um listener delegado no documento em vez de uma diretiva por painel: o
 * `closest('.card')` já encontra qualquer painel, inclusive os que forem
 * montados depois, e o template não precisa marcar nada. Grava a posição em
 * duas variáveis CSS e deixa o desenho do brilho para o CSS — um
 * `setProperty` por evento é mais barato e mais fluido que criar tweens que se
 * cancelam a cada movimento de mouse.
 */
export function bindPanelLight(): void {
  if (typeof document === 'undefined' || !hasFinePointer() || prefersReducedMotion()) return
  document.addEventListener(
    'pointermove',
    (event) => {
      const panel = (event.target as Element | null)?.closest?.('.card') as HTMLElement | null
      if (!panel) return
      const box = panel.getBoundingClientRect()
      panel.style.setProperty('--mx', `${event.clientX - box.left}px`)
      panel.style.setProperty('--my', `${event.clientY - box.top}px`)
      panel.dataset.lit = 'on'
    },
    { passive: true },
  )
}

/* -------------------------------------------------------------------------- */
/* Números                                                                     */
/* -------------------------------------------------------------------------- */

/**
 * Número que corre até o valor.
 *
 * Roda o formatador a cada quadro em vez de interpolar a string, senão o
 * separador de milhar pt-BR pisca. Valor nulo não anima: ausência de dado é
 * um traço, não um zero que sobe.
 */
export function countTo(
  el: HTMLElement,
  value: number,
  format: (value: number) => string,
  duration = 1.1,
): void {
  if (prefersReducedMotion()) {
    el.textContent = format(value)
    return
  }
  const state = { current: 0 }
  gsap.to(state, {
    current: value,
    duration,
    ease: EASE,
    onUpdate: () => {
      el.textContent = format(state.current)
    },
    onComplete: () => {
      el.textContent = format(value)
    },
  })
}

export { ScrollTrigger }
