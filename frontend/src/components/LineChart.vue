<script setup lang="ts">
/**
 * Gráfico de linha/área em SVG.
 *
 * Aceita várias séries e marca pontos "parciais" (mês incompleto, ano em
 * andamento) com traço interrompido — assim uma queda causada por dado
 * faltante não se confunde com queda real.
 *
 * O desenho é feito na largura REAL do contêiner (medida por
 * ResizeObserver), não numa prancheta fixa encolhida por `viewBox`. Encolher
 * 760px para a tela de um celular reduzia o texto dos eixos de 10px para ~4px.
 * Agora 11px de fonte são 11px na tela, e a quantidade de rótulos no eixo X
 * acompanha o espaço disponível.
 *
 * Leitura por ponteiro: mouse passa por cima; no toque, encostar ou arrastar
 * o dedo na horizontal escolhe o ponto (a rolagem vertical continua livre).
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { gsap } from 'gsap'
import type { Series } from './chart'
import { EASE, hasFinePointer, prefersReducedMotion } from '@/motion'

const props = withDefaults(
  defineProps<{
    series: Series[]
    formatValue?: (value: number) => string
    formatX?: (value: string) => string
    height?: number
    area?: boolean
    yZero?: boolean
  }>(),
  {
    formatValue: (value: number) => value.toLocaleString('pt-BR'),
    formatX: (value: string) => value,
    height: 260,
    area: true,
    yZero: true,
  },
)

const host = ref<HTMLElement | null>(null)
const width = ref(760)
let observer: ResizeObserver | null = null

onMounted(() => {
  if (!host.value) return
  width.value = Math.round(host.value.clientWidth) || 760
  observer = new ResizeObserver(([entry]) => {
    const next = Math.round(entry.contentRect.width)
    if (next > 0 && next !== width.value) width.value = next
  })
  observer.observe(host.value)
})
onBeforeUnmount(() => observer?.disconnect())

const narrow = computed(() => width.value < 480)
/** No celular, um gráfico de 260px de altura ocupa meia tela para pouca linha. */
const chartHeight = computed(() => (narrow.value ? Math.min(props.height, 200) : props.height))
const PAD = computed(() => ({ top: 12, right: narrow.value ? 8 : 16, bottom: 26, left: narrow.value ? 42 : 52 }))

const fine = hasFinePointer()
const hoverIndex = ref<number | null>(null)

const labels = computed(() => props.series[0]?.points.map((point) => point.x) ?? [])

const bounds = computed(() => {
  const values = props.series
    .flatMap((serie) => serie.points.map((point) => point.y))
    .filter((value): value is number => value !== null)
  if (values.length === 0) return { min: 0, max: 1 }
  const max = Math.max(...values)
  const min = props.yZero ? Math.min(0, ...values) : Math.min(...values)
  // Folga de 8% no topo para o rótulo não encostar na borda.
  const headroom = (max - min) * 0.08 || 1
  return { min, max: max + headroom }
})

function xAt(index: number): number {
  const count = Math.max(labels.value.length - 1, 1)
  const pad = PAD.value
  return pad.left + (index / count) * (width.value - pad.left - pad.right)
}

function yAt(value: number): number {
  const { min, max } = bounds.value
  const ratio = (value - min) / (max - min || 1)
  const pad = PAD.value
  return chartHeight.value - pad.bottom - ratio * (chartHeight.value - pad.top - pad.bottom)
}

/** Trechos contínuos (índices com valor). Um buraco (null) encerra o trecho. */
function runsOf(serie: Series): number[][] {
  const runs: number[][] = []
  let current: number[] = []
  serie.points.forEach((point, index) => {
    if (point.y === null) {
      if (current.length) runs.push(current)
      current = []
    } else {
      current.push(index)
    }
  })
  if (current.length) runs.push(current)
  return runs
}

function pathOf(serie: Series, run: number[]): string {
  return run
    .map((index, order) => `${order === 0 ? 'M' : 'L'}${xAt(index).toFixed(1)},${yAt(serie.points[index].y as number).toFixed(1)}`)
    .join('')
}

/** Linhas: um buraco quebra a linha em vez de interpolá-la. */
function segmentsOf(serie: Series): string[] {
  return runsOf(serie).filter((run) => run.length > 1).map((run) => pathOf(serie, run))
}

/**
 * Pontos sem vizinho com valor. Sem isto, um ano completo cercado de lacunas
 * (ex.: 2014 e 2021 nas matrículas) não desenharia nada — o dado existiria e
 * o gráfico o esconderia.
 */
function isolatedOf(serie: Series): number[] {
  return runsOf(serie).filter((run) => run.length === 1).map((run) => run[0])
}

/** Área por trecho: preencher por cima de uma lacuna seria interpolar. */
function areaOf(serie: Series): string {
  const baseline = yAt(bounds.value.min).toFixed(1)
  return runsOf(serie)
    .filter((run) => run.length > 1)
    .map((run) => {
      const first = xAt(run[0]).toFixed(1)
      const last = xAt(run[run.length - 1]).toFixed(1)
      return `${pathOf(serie, run)}L${last},${baseline}L${first},${baseline}Z`
    })
    .join('')
}

const ticks = computed(() => {
  const { min, max } = bounds.value
  return Array.from({ length: 4 }, (_, step) => {
    const value = min + ((max - min) * step) / 3
    return { value, y: yAt(value) }
  })
})

const xTicks = computed(() => {
  const count = labels.value.length
  if (count === 0) return []
  // Um rótulo a cada ~72px: 4 no celular, 10 no desktop largo.
  const slots = Math.max(3, Math.floor((width.value - PAD.value.left) / 72))
  const stride = Math.max(1, Math.ceil(count / slots))
  const last = count - 1
  // O último rótulo sempre aparece; o do passo anterior sai se ficar colado
  // nele (evita "20252026" e "jul/26set/26").
  return labels.value
    .map((label, index) => ({ label, index }))
    .filter(({ index }) => index === last || (index % stride === 0 && last - index >= stride * 0.6))
})

const svg = ref<SVGSVGElement | null>(null)

/**
 * A linha é traçada da esquerda para a direita, como uma pena de plotter.
 * O desenho leva o mesmo tempo independente do número de pontos, então séries
 * longas e curtas terminam juntas e a página assenta de uma vez.
 */
watch(
  () => props.series,
  async () => {
    if (prefersReducedMotion()) return
    await nextTick()
    const lines = svg.value?.querySelectorAll<SVGPathElement>('[data-line]')
    if (!lines?.length) return
    lines.forEach((line) => {
      const length = line.getTotalLength()
      gsap.fromTo(
        line,
        { strokeDasharray: length, strokeDashoffset: length },
        {
          strokeDashoffset: 0,
          duration: 0.9,
          ease: EASE,
          clearProps: 'strokeDasharray,strokeDashoffset',
        },
      )
    })
  },
  { immediate: true, deep: false },
)

function pick(event: PointerEvent) {
  const rect = (event.currentTarget as SVGElement).getBoundingClientRect()
  const x = event.clientX - rect.left
  const count = Math.max(labels.value.length - 1, 1)
  const pad = PAD.value
  const index = Math.round(((x - pad.left) / (width.value - pad.left - pad.right)) * count)
  hoverIndex.value = Math.min(Math.max(index, 0), labels.value.length - 1)
}

function onMove(event: PointerEvent) {
  // Mouse: sempre. Toque: só enquanto o dedo está encostado (arrastar).
  if (event.pointerType === 'mouse' || event.buttons > 0) pick(event)
}

function onLeave(event: PointerEvent) {
  // No toque o ponto escolhido fica, para ser lido depois de tirar o dedo.
  if (event.pointerType === 'mouse') hoverIndex.value = null
}
</script>

<template>
  <div ref="host">
    <div v-if="series.length > 1" class="mb-4 flex flex-wrap gap-x-5 gap-y-2">
      <span v-for="serie in series" :key="serie.key" class="flex items-center gap-2">
        <span class="h-[3px] w-5" :style="{ background: serie.color }" />
        <span class="label">{{ serie.label }}</span>
      </span>
    </div>

    <svg
      ref="svg"
      :viewBox="`0 0 ${width} ${chartHeight}`"
      :width="width"
      :height="chartHeight"
      class="block max-w-full select-none overflow-visible"
      style="touch-action: pan-y"
      @pointerdown="pick"
      @pointermove="onMove"
      @pointerleave="onLeave"
    >
      <defs>
        <linearGradient v-for="serie in series" :id="`grad-${serie.key}`" :key="serie.key" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" :stop-color="serie.color" stop-opacity="0.28" />
          <stop offset="100%" :stop-color="serie.color" stop-opacity="0" />
        </linearGradient>
      </defs>

      <g>
        <line
          v-for="tick in ticks"
          :key="`grid-${tick.value}`"
          :x1="PAD.left"
          :x2="width - PAD.right"
          :y1="tick.y"
          :y2="tick.y"
          stroke="#1E0B38"
          stroke-width="1"
        />
        <text
          v-for="tick in ticks"
          :key="`lab-${tick.value}`"
          :x="PAD.left - 8"
          :y="tick.y + 4"
          text-anchor="end"
          class="fill-faint font-mono text-[11px] tnum"
        >
          {{ formatValue(tick.value) }}
        </text>
      </g>

      <g v-for="serie in series" :key="`serie-${serie.key}`">
        <path v-if="area" :d="areaOf(serie)" :fill="`url(#grad-${serie.key})`" />
        <path
          v-for="(segment, index) in segmentsOf(serie)"
          :key="`seg-${serie.key}-${index}`"
          data-line
          :d="segment"
          fill="none"
          :stroke="serie.color"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <circle
          v-for="index in isolatedOf(serie)"
          :key="`solo-${serie.key}-${index}`"
          :cx="xAt(index)"
          :cy="yAt(serie.points[index].y as number)"
          r="3.5"
          :fill="serie.color"
        />
        <circle
          v-for="(point, index) in serie.points"
          v-show="point.y !== null && hoverIndex === index"
          :key="`dot-${serie.key}-${index}`"
          :cx="xAt(index)"
          :cy="yAt(point.y ?? 0)"
          r="4"
          :fill="serie.color"
          stroke="#060010"
          stroke-width="2"
        />
      </g>

      <line
        v-if="hoverIndex !== null"
        :x1="xAt(hoverIndex)"
        :x2="xAt(hoverIndex)"
        :y1="PAD.top"
        :y2="chartHeight - PAD.bottom"
        stroke="#FF006A"
        stroke-width="1"
        stroke-dasharray="3 3"
      />

      <text
        v-for="tick in xTicks"
        :key="`x-${tick.index}`"
        :x="xAt(tick.index)"
        :y="chartHeight - 7"
        :text-anchor="tick.index === labels.length - 1 ? 'end' : tick.index === 0 ? 'start' : 'middle'"
        class="fill-faint font-mono text-[11px]"
      >
        {{ formatX(tick.label) }}
      </text>
    </svg>

    <!-- Altura mínima reservada: a leitura aparecer não pode empurrar a página. -->
    <p v-if="hoverIndex === null" class="mt-2 min-h-[1.25rem] font-mono text-[10px] uppercase tracking-[0.1em] text-faint/70">
      {{ fine ? 'Passe o cursor para ler os valores' : 'Toque ou arraste no gráfico para ler os valores' }}
    </p>
    <div v-else class="mt-2 flex min-h-[1.25rem] flex-wrap items-baseline gap-x-4 gap-y-1 text-xs" aria-live="polite">
      <span class="text-faint">{{ formatX(labels[hoverIndex]) }}</span>
      <span v-for="serie in series" :key="`tip-${serie.key}`" class="tnum text-muted">
        <span class="text-ink" :style="{ color: serie.color }">{{ serie.label }}</span>
        {{
          serie.points[hoverIndex]?.y === null || serie.points[hoverIndex]?.y === undefined
            ? '—'
            : formatValue(serie.points[hoverIndex].y as number)
        }}
        <span v-if="serie.points[hoverIndex]?.partial" class="text-warn">(parcial)</span>
      </span>
    </div>
  </div>
</template>
