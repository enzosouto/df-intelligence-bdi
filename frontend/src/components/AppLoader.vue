<script setup lang="ts">
/**
 * Tela de carregamento.
 *
 * O fundo é um campo de dados em varredura — mas não é ruído decorativo: os
 * tokens que piscam são o alfabeto real do projeto (RA-I a RA-XXXV, os anos da
 * série da SSP-DF, CVLI, CNES, IBGE, os códigos das fontes). Quem lê o fundo
 * está lendo o vocabulário do que está sendo carregado.
 *
 * No centro, a malha é plotada célula a célula enquanto as requisições
 * resolvem, e cada endpoint aparece com o seu status de verdade — não há barra
 * de progresso falsa contando sozinha até 100%.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { gsap } from 'gsap'
import { EASE, prefersReducedMotion } from '@/motion'

const props = defineProps<{
  steps: { label: string; status: 'pending' | 'ok' | 'fail' }[]
  ready: boolean
}>()

const emit = defineEmits<{ done: [] }>()

const root = ref<HTMLElement | null>(null)
const rows = ref<string[]>([])

/** Quantas linhas cabem na altura da tela (16px de linha + 4px de intervalo). */
function rowCount(): number {
  return Math.ceil((typeof window === 'undefined' ? 720 : window.innerHeight) / 20) + 1
}

/**
 * Tempo mínimo em tela. As duas requisições do boot voltam em ~200ms em
 * localhost, e um loader que pisca por 200ms é pior que loader nenhum: a
 * página dá um salto e ninguém entende o que aconteceu. Três segundos é o
 * suficiente para a malha terminar de plotar e para os status aparecerem.
 */
const MINIMUM_MS = 3000
const mountedAt = Date.now()

/**
 * Largura da linha em caracteres, medida a cada linha gerada.
 *
 * Ler `innerWidth` aqui em vez de fixar um número faz o campo cobrir a tela
 * inteira em qualquer largura — e, como as linhas são regeradas a cada 90ms,
 * girar o celular durante o carregamento se ajusta sozinho, sem listener de
 * resize. (6px é a largura do dígito do IBM Plex Mono em 10px.)
 */
function rowLength(): number {
  return Math.ceil((typeof window === 'undefined' ? 720 : window.innerWidth) / 6) + 4
}

/** O alfabeto do projeto. Nada aqui é inventado para parecer técnico. */
const TOKENS = [
  ...Array.from({ length: 35 }, (_, index) => `RA-${romanOf(index + 1)}`),
  ...Array.from({ length: 13 }, (_, index) => String(2014 + index)),
  'CVLI',
  'CCP',
  'CNES',
  'IBGE',
  'SIDRA',
  'SSP-DF',
  'SEEDF',
  'IDE-DF',
  'IBRAM',
  'ERA5',
  'N11',
  'CENSO',
  'MATRÍCULA',
  'CICLOVIA',
  'SUBDISTRITO',
  '—',
]

function romanOf(value: number): string {
  const table: [number, string][] = [
    [10, 'X'],
    [9, 'IX'],
    [5, 'V'],
    [4, 'IV'],
    [1, 'I'],
  ]
  let rest = value
  let out = ''
  for (const [amount, symbol] of table) {
    while (rest >= amount) {
      out += symbol
      rest -= amount
    }
  }
  return out
}

function buildRow(): string {
  const length = rowLength()
  let row = ''
  while (row.length < length) {
    row += `${TOKENS[Math.floor(Math.random() * TOKENS.length)]}  `
  }
  return row.slice(0, length)
}

let scrambleTimer: number | undefined

const allSettled = computed(() => props.steps.every((step) => step.status !== 'pending'))

function leave() {
  const element = root.value
  if (!element) return emit('done')

  if (prefersReducedMotion()) {
    emit('done')
    return
  }

  gsap
    .timeline({ onComplete: () => emit('done') })
    .to('[data-loader-row]', {
      opacity: 0,
      duration: 0.3,
      ease: 'none',
      stagger: { each: 0.012, from: 'edges' },
    })
    .to('[data-loader-core]', { y: -12, opacity: 0, duration: 0.4, ease: EASE }, '-=0.2')
    .to(element, { opacity: 0, duration: 0.35, ease: 'none' }, '-=0.15')
}

onMounted(() => {
  rows.value = Array.from({ length: rowCount() }, buildRow)

  if (!prefersReducedMotion()) {
    // Só algumas linhas por vez: o campo tem que parecer leitura chegando,
    // não uma tela inteira trocando de conteúdo a cada quadro.
    scrambleTimer = window.setInterval(() => {
      const next = [...rows.value]
      for (let count = 0; count < 3; count += 1) {
        next[Math.floor(Math.random() * next.length)] = buildRow()
      }
      rows.value = next
    }, 90)

    gsap.fromTo(
      '[data-loader-cell]',
      { opacity: 0, scale: 0.3 },
      {
        opacity: 1,
        scale: 1,
        duration: 0.5,
        ease: EASE,
        stagger: { each: 0.006, from: 'center' },
      },
    )
  }
})

onBeforeUnmount(() => window.clearInterval(scrambleTimer))

watch(
  () => props.ready && allSettled.value,
  (finished) => {
    if (!finished) return
    if (prefersReducedMotion()) {
      window.clearInterval(scrambleTimer)
      leave()
      return
    }
    // O campo continua varrendo até o fim: parar o scramble aqui congelaria a
    // tela no último segundo, que é justamente quando alguém está olhando.
    const remaining = Math.max(0, MINIMUM_MS - (Date.now() - mountedAt))
    window.setTimeout(() => {
      window.clearInterval(scrambleTimer)
      leave()
    }, remaining)
  },
  { immediate: true },
)
</script>

<template>
  <div
    ref="root"
    class="fixed inset-0 z-[200] flex items-center justify-center overflow-hidden bg-night"
    role="status"
    aria-live="polite"
  >
    <!-- Campo de dados em varredura -->
    <div class="pointer-events-none absolute inset-0 flex flex-col justify-center gap-1 px-2">
      <p
        v-for="(row, index) in rows"
        :key="index"
        data-loader-row
        class="whitespace-pre font-mono text-[10px] leading-4 text-ink"
        :style="{ opacity: 0.05 + (index % 5) * 0.012 }"
      >
        {{ row }}
      </p>
    </div>

    <!-- Gradiente que mantém o miolo legível sobre o campo -->
    <div
      class="pointer-events-none absolute inset-0"
      style="background: radial-gradient(28rem 20rem at 50% 50%, #060010 40%, transparent 100%)"
    />

    <div data-loader-core class="relative w-full max-w-md px-6 text-center">
      <p class="label">Carregando</p>
      <p
        class="mt-3 font-display text-2xl font-bold uppercase tracking-tight sm:text-3xl"
        style="font-stretch: 118%"
      >
        DF Intelligence
      </p>

      <!-- A malha, plotada enquanto o dado vem -->
      <div class="mt-7 flex justify-center">
        <svg viewBox="0 0 451 14" class="h-auto w-full max-w-[451px]" aria-hidden="true">
          <g v-for="module in 35" :key="module" :transform="`translate(${(module - 1) * 13} 0)`">
            <rect
              v-for="cell in 6"
              :key="cell"
              data-loader-cell
              :x="((cell - 1) % 2) * 5"
              :y="Math.floor((cell - 1) / 2) * 5"
              width="4"
              height="4"
              fill="#F7F2FF"
              fill-opacity="0.8"
            />
          </g>
        </svg>
      </div>

      <ul class="mt-7 space-y-1.5 text-left">
        <li
          v-for="step in steps"
          :key="step.label"
          class="flex items-center justify-between gap-3 font-mono text-[10px] uppercase tracking-[0.12em]"
        >
          <span class="text-faint">{{ step.label }}</span>
          <span
            :class="{
              'text-faint': step.status === 'pending',
              'text-education': step.status === 'ok',
              'text-security': step.status === 'fail',
            }"
          >
            <span v-if="step.status === 'pending'" class="animate-blink">aguardando</span>
            <span v-else-if="step.status === 'ok'">200</span>
            <span v-else>falhou</span>
          </span>
        </li>
      </ul>

      <p class="mt-7 label">35 Regiões Administrativas · 6 domínios</p>

      <p class="mt-5 border-t border-line pt-5 font-mono text-[10px] uppercase tracking-[0.12em]">
        <span class="text-accent">Enzo Souto</span>
        <span class="text-faint"> · Analista de dados</span>
      </p>
    </div>
  </div>
</template>
