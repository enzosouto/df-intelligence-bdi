<script setup lang="ts">
/**
 * Mapa das Regiões Administrativas em SVG puro.
 *
 * Não usa biblioteca de mapas: são 35 polígonos estáticos em um recorte fixo,
 * e uma projeção equirretangular com correção de latitude é exata o bastante
 * nessa escala (o DF cabe em ~0,9° de latitude). Em troca, o mapa herda o
 * sistema visual inteiro — cores, transições, foco de teclado — sem CSS de
 * terceiros para sobrescrever.
 *
 * Regiões sem valor para o indicador escolhido ficam hachuradas, nunca
 * pintadas como se fossem zero.
 */
import { computed, ref } from 'vue'
import type { RegionFeature } from '@/types'
import { EMPTY } from '@/format'

const props = withDefaults(
  defineProps<{
    features: RegionFeature[]
    metricOf: (feature: RegionFeature) => number | null
    formatValue: (value: number | null) => string
    color?: string
    selectedId?: string | null
    metricLabel?: string
  }>(),
  { color: '#5EE6C5', selectedId: null, metricLabel: '' },
)

const emit = defineEmits<{ select: [regionId: string]; hover: [regionId: string | null] }>()

const WIDTH = 920
const HEIGHT = 720
const PADDING = 16

const hovered = ref<string | null>(null)
const pointer = ref({ x: 0, y: 0 })

/** Anéis externos de cada feature, já como lista de polígonos. */
function ringsOf(feature: RegionFeature): number[][][] {
  return feature.geometry.type === 'Polygon'
    ? feature.geometry.coordinates
    : feature.geometry.coordinates.flat()
}

const projection = computed(() => {
  let minLon = Infinity
  let maxLon = -Infinity
  let minLat = Infinity
  let maxLat = -Infinity

  for (const feature of props.features) {
    for (const ring of ringsOf(feature)) {
      for (const [lon, lat] of ring) {
        if (lon < minLon) minLon = lon
        if (lon > maxLon) maxLon = lon
        if (lat < minLat) minLat = lat
        if (lat > maxLat) maxLat = lat
      }
    }
  }

  // Um grau de longitude é mais curto que um de latitude fora do equador.
  // Sem esse fator o DF sai esticado na horizontal.
  const lonScale = Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180)
  const spanX = (maxLon - minLon) * lonScale
  const spanY = maxLat - minLat
  const scale = Math.min((WIDTH - PADDING * 2) / spanX, (HEIGHT - PADDING * 2) / spanY)
  const offsetX = (WIDTH - spanX * scale) / 2
  const offsetY = (HEIGHT - spanY * scale) / 2

  return (lon: number, lat: number): [number, number] => [
    offsetX + (lon - minLon) * lonScale * scale,
    offsetY + (maxLat - lat) * scale,
  ]
})

/** Escala por posto (quantil), robusta a outliers como o SIA. */
const scaleByRank = computed(() => {
  const values = props.features
    .map((feature) => props.metricOf(feature))
    .filter((value): value is number => value !== null)
    .sort((a, b) => a - b)

  return (value: number | null): number => {
    if (value === null || values.length === 0) return 0
    const rank = values.filter((candidate) => candidate <= value).length
    return rank / values.length
  }
})

const shapes = computed(() =>
  props.features.map((feature) => {
    const value = props.metricOf(feature)
    const intensity = scaleByRank.value(value)
    return {
      id: feature.properties.region_id,
      name: feature.properties.region_name,
      value,
      // Piso de 0,08 para que a região mais baixa ainda se leia como área.
      fillOpacity: value === null ? 0 : 0.08 + intensity * 0.82,
      path: ringsOf(feature)
        .map(
          (ring) =>
            ring
              .map(([lon, lat], index) => {
                const [x, y] = projection.value(lon, lat)
                return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
              })
              .join('') + 'Z',
        )
        .join(' '),
    }
  }),
)

const hoveredShape = computed(() => shapes.value.find((shape) => shape.id === hovered.value) ?? null)

function onEnter(id: string) {
  hovered.value = id
  emit('hover', id)
}

function onLeave() {
  hovered.value = null
  emit('hover', null)
}

function onMove(event: MouseEvent) {
  const host = (event.currentTarget as HTMLElement).getBoundingClientRect()
  pointer.value = { x: event.clientX - host.left, y: event.clientY - host.top }
}
</script>

<template>
  <div class="relative" @mousemove="onMove" @mouseleave="onLeave">
    <svg
      :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
      class="h-auto w-full"
      role="img"
      :aria-label="`Mapa das Regiões Administrativas do Distrito Federal por ${metricLabel || 'indicador selecionado'}`"
    >
      <defs>
        <pattern
          id="no-data"
          width="6"
          height="6"
          patternTransform="rotate(45)"
          patternUnits="userSpaceOnUse"
        >
          <rect width="6" height="6" fill="#0F1115" />
          <line x1="0" y1="0" x2="0" y2="6" stroke="#2A3140" stroke-width="2" />
        </pattern>
      </defs>

      <g>
        <path
          v-for="shape in shapes"
          :key="shape.id"
          :d="shape.path"
          :fill="shape.value === null ? 'url(#no-data)' : color"
          :fill-opacity="shape.value === null ? 1 : shape.fillOpacity"
          :stroke="
            selectedId === shape.id ? '#ECEFF4' : hovered === shape.id ? color : '#080A0C'
          "
          :stroke-width="selectedId === shape.id ? 2.4 : hovered === shape.id ? 2 : 1"
          class="cursor-pointer transition-[stroke,stroke-width,fill-opacity] duration-200 focus:outline-none"
          tabindex="0"
          role="button"
          :aria-label="`${shape.name}: ${formatValue(shape.value)}`"
          @mouseenter="onEnter(shape.id)"
          @focus="onEnter(shape.id)"
          @blur="onLeave"
          @click="emit('select', shape.id)"
          @keydown.enter.prevent="emit('select', shape.id)"
          @keydown.space.prevent="emit('select', shape.id)"
        />
      </g>
    </svg>

    <Transition
      enter-active-class="transition duration-150"
      enter-from-class="opacity-0 translate-y-1"
      leave-active-class="transition duration-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="hoveredShape"
        class="pointer-events-none absolute z-20 -translate-x-1/2 -translate-y-[calc(100%+14px)]
               whitespace-nowrap rounded-xl border border-line bg-elevated/95 px-3 py-2
               shadow-card backdrop-blur"
        :style="{ left: `${pointer.x}px`, top: `${pointer.y}px` }"
      >
        <p class="font-display text-sm font-semibold text-ink">{{ hoveredShape.name }}</p>
        <p class="tnum text-xs text-muted">
          <span v-if="hoveredShape.value === null" class="text-warn">Sem dado publicado</span>
          <span v-else>{{ formatValue(hoveredShape.value) }}</span>
        </p>
      </div>
    </Transition>

    <div class="mt-4 flex flex-wrap items-center gap-4 text-[11px] text-faint">
      <div class="flex items-center gap-2">
        <span class="uppercase tracking-[0.14em]">menor</span>
        <div class="flex overflow-hidden rounded-full border border-line">
          <span
            v-for="step in 6"
            :key="step"
            class="h-2.5 w-7"
            :style="{ background: color, opacity: 0.08 + ((step - 1) / 5) * 0.82 }"
          />
        </div>
        <span class="uppercase tracking-[0.14em]">maior</span>
      </div>
      <div class="flex items-center gap-2">
        <svg width="14" height="14" class="rounded-[3px]">
          <rect width="14" height="14" fill="url(#no-data)" />
        </svg>
        <span>sem dado publicado ({{ EMPTY }})</span>
      </div>
    </div>
  </div>
</template>
