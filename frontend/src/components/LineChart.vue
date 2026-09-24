<script setup lang="ts">
/**
 * Gráfico de linha/área em SVG.
 *
 * Aceita várias séries e marca pontos "parciais" (mês incompleto, ano em
 * andamento) com traço interrompido — assim uma queda causada por dado
 * faltante não se confunde com queda real.
 */
import { computed, ref } from 'vue'
import type { Series } from './chart'

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

const WIDTH = 760
const PAD = { top: 16, right: 16, bottom: 28, left: 52 }

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
  return PAD.left + (index / count) * (WIDTH - PAD.left - PAD.right)
}

function yAt(value: number): number {
  const { min, max } = bounds.value
  const ratio = (value - min) / (max - min || 1)
  return props.height - PAD.bottom - ratio * (props.height - PAD.top - PAD.bottom)
}

/** Segmentos contínuos: um buraco (null) quebra a linha em vez de interpolá-la. */
function segmentsOf(serie: Series): string[] {
  const segments: string[] = []
  let current: string[] = []
  serie.points.forEach((point, index) => {
    if (point.y === null) {
      if (current.length > 1) segments.push(current.join(''))
      current = []
      return
    }
    current.push(`${current.length === 0 ? 'M' : 'L'}${xAt(index).toFixed(1)},${yAt(point.y).toFixed(1)}`)
  })
  if (current.length > 1) segments.push(current.join(''))
  return segments
}

function areaOf(serie: Series): string {
  const points = serie.points
    .map((point, index) => ({ point, index }))
    .filter(({ point }) => point.y !== null)
  if (points.length < 2) return ''
  const line = points
    .map(({ point, index }, order) => `${order === 0 ? 'M' : 'L'}${xAt(index)},${yAt(point.y as number)}`)
    .join('')
  const first = xAt(points[0].index)
  const last = xAt(points[points.length - 1].index)
  const baseline = yAt(bounds.value.min)
  return `${line}L${last},${baseline}L${first},${baseline}Z`
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
  const stride = Math.max(1, Math.ceil(count / 7))
  return labels.value
    .map((label, index) => ({ label, index }))
    .filter(({ index }) => index % stride === 0 || index === count - 1)
})

function onMove(event: MouseEvent) {
  const rect = (event.currentTarget as SVGElement).getBoundingClientRect()
  const ratio = (event.clientX - rect.left) / rect.width
  const x = ratio * WIDTH
  const count = Math.max(labels.value.length - 1, 1)
  const index = Math.round(
    ((x - PAD.left) / (WIDTH - PAD.left - PAD.right)) * count,
  )
  hoverIndex.value = Math.min(Math.max(index, 0), labels.value.length - 1)
}
</script>

<template>
  <div>
    <div v-if="series.length > 1" class="mb-3 flex flex-wrap gap-x-5 gap-y-2">
      <span v-for="serie in series" :key="serie.key" class="flex items-center gap-2 text-xs text-muted">
        <span class="h-0.5 w-4 rounded-full" :style="{ background: serie.color }" />
        {{ serie.label }}
      </span>
    </div>

    <svg
      :viewBox="`0 0 ${WIDTH} ${height}`"
      class="h-auto w-full overflow-visible"
      @mousemove="onMove"
      @mouseleave="hoverIndex = null"
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
          :x2="WIDTH - PAD.right"
          :y1="tick.y"
          :y2="tick.y"
          stroke="#1A1F28"
          stroke-width="1"
        />
        <text
          v-for="tick in ticks"
          :key="`lab-${tick.value}`"
          :x="PAD.left - 10"
          :y="tick.y + 4"
          text-anchor="end"
          class="fill-faint text-[11px] tnum"
        >
          {{ formatValue(tick.value) }}
        </text>
      </g>

      <g v-for="serie in series" :key="`serie-${serie.key}`">
        <path v-if="area" :d="areaOf(serie)" :fill="`url(#grad-${serie.key})`" />
        <path
          v-for="(segment, index) in segmentsOf(serie)"
          :key="`seg-${serie.key}-${index}`"
          :d="segment"
          fill="none"
          :stroke="serie.color"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <circle
          v-for="(point, index) in serie.points"
          v-show="point.y !== null && hoverIndex === index"
          :key="`dot-${serie.key}-${index}`"
          :cx="xAt(index)"
          :cy="yAt(point.y ?? 0)"
          r="4"
          :fill="serie.color"
          stroke="#08090B"
          stroke-width="2"
        />
      </g>

      <line
        v-if="hoverIndex !== null"
        :x1="xAt(hoverIndex)"
        :x2="xAt(hoverIndex)"
        :y1="PAD.top"
        :y2="height - PAD.bottom"
        stroke="#39414F"
        stroke-width="1"
        stroke-dasharray="3 3"
      />

      <text
        v-for="tick in xTicks"
        :key="`x-${tick.index}`"
        :x="xAt(tick.index)"
        :y="height - 8"
        text-anchor="middle"
        class="fill-faint text-[11px]"
      >
        {{ formatX(tick.label) }}
      </text>
    </svg>

    <div v-if="hoverIndex !== null" class="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-xs">
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
