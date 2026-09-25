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
import { computed, nextTick, ref, watch } from 'vue'
import { gsap } from 'gsap'
import type { RegionFeature } from '@/types'
import { EMPTY } from '@/format'
import { EASE, prefersReducedMotion } from '@/motion'

const props = withDefaults(
  defineProps<{
    features: RegionFeature[]
    metricOf: (feature: RegionFeature) => number | null
    formatValue: (value: number | null) => string
    color?: string
    selectedId?: string | null
    metricLabel?: string
  }>(),
  { color: '#FFFFFF', selectedId: null, metricLabel: '' },
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
    const firstRing = ringsOf(feature)[0] ?? []
    const centroidLon =
      firstRing.reduce((sum, [lon]) => sum + lon, 0) / Math.max(firstRing.length, 1)
    return {
      id: feature.properties.region_id,
      name: feature.properties.region_name,
      value,
      // Só para ordenar a cascata de oeste para leste na troca de métrica.
      cx: projection.value(centroidLon, 0)[0],
      // Piso de 0,14: abaixo disso a RA de menor valor some no fundo carvão.
      fillOpacity: value === null ? 0 : 0.14 + intensity * 0.76,
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

const svg = ref<SVGSVGElement | null>(null)

/**
 * Trocar de métrica repinta o mapa numa onda de oeste para leste, na ordem em
 * que as RAs aparecem no eixo. Um corte seco faria 35 polígonos mudarem de cor
 * ao mesmo tempo e ninguém veria o que mudou; a onda obriga o olho a percorrer
 * a cidade inteira antes de parar no valor.
 */
watch(
  shapes,
  async () => {
    if (prefersReducedMotion()) return
    await nextTick()
    const paths = svg.value?.querySelectorAll<SVGPathElement>('[data-region]')
    if (!paths?.length) return
    const ordered = [...paths].sort(
      (a, b) => Number(a.dataset.cx ?? 0) - Number(b.dataset.cx ?? 0),
    )
    gsap.fromTo(
      ordered,
      { fillOpacity: 0 },
      {
        fillOpacity: (_index: number, target: SVGPathElement) =>
          Number(target.getAttribute('fill-opacity') ?? 1),
        duration: 0.45,
        ease: EASE,
        stagger: 0.012,
        clearProps: 'fillOpacity',
      },
    )
  },
  { immediate: true },
)

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
      ref="svg"
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
          <rect width="6" height="6" fill="#0C0320" />
          <line x1="0" y1="0" x2="0" y2="6" stroke="#FF006A" stroke-width="2" />
        </pattern>
      </defs>

      <g>
        <path
          v-for="shape in shapes"
          :key="shape.id"
          data-region
          :data-cx="shape.cx"
          :d="shape.path"
          :fill="shape.value === null ? 'url(#no-data)' : color"
          :fill-opacity="shape.value === null ? 1 : shape.fillOpacity"
          :stroke="
            selectedId === shape.id ? '#F7F2FF' : hovered === shape.id ? color : '#2C1549'
          "
          :stroke-width="selectedId === shape.id ? 2.4 : hovered === shape.id ? 2 : 1"
          class="cursor-pointer transition-[stroke,stroke-width] duration-200 focus:outline-none"
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
               whitespace-nowrap border border-line bg-elevated px-3 py-2"
        :style="{ left: `${pointer.x}px`, top: `${pointer.y}px` }"
      >
        <p class="font-mono text-[10px] uppercase tracking-[0.12em] text-ink">
          {{ hoveredShape.name }}
        </p>
        <p class="mt-0.5 font-display text-sm font-semibold tnum" style="font-stretch: 112%">
          <span v-if="hoveredShape.value === null" class="text-warn">Sem dado publicado</span>
          <span v-else class="text-ink">{{ formatValue(hoveredShape.value) }}</span>
        </p>
      </div>
    </Transition>

    <div class="mt-5 flex flex-wrap items-center gap-6">
      <div class="flex items-center gap-2">
        <span class="label">menor</span>
        <div class="flex gap-px">
          <span
            v-for="step in 6"
            :key="step"
            class="h-2.5 w-7"
            :style="{ background: color, opacity: 0.14 + ((step - 1) / 5) * 0.76 }"
          />
        </div>
        <span class="label">maior</span>
      </div>
      <div class="flex items-center gap-2">
        <svg width="12" height="12" aria-hidden="true">
          <rect width="12" height="12" fill="url(#no-data)" />
        </svg>
        <span class="label">sem dado publicado ({{ EMPTY }})</span>
      </div>
    </div>
  </div>
</template>
