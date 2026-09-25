<script setup lang="ts">
/**
 * A malha — o mapa de cobertura como painel modular.
 *
 * 35 módulos, um por Região Administrativa, na ordem oficial (RA-I … RA-XXXV).
 * Cada módulo tem seis células, uma por domínio publicado: preenchida quando a
 * fonte publica para aquela RA, vazia quando não publica.
 *
 * A referência é Athos Bulcão, cujos painéis de Brasília fazem variação a
 * partir de um módulo único repetido. Aqui a variação não é combinatória: é a
 * cobertura real. O desenho que emerge é o buraco das fontes públicas — o
 * assunto do projeto, virado identidade.
 *
 * Acessibilidade: a malha é navegação redundante (o mapa e o ranking já levam
 * a qualquer RA pelo teclado), então ela se apresenta como uma figura única
 * com resumo em `aria-label`, em vez de despejar 35 paradas de tabulação no
 * cabeçalho.
 */
import { computed, ref, watch } from 'vue'
import { gsap } from 'gsap'
import { prefersReducedMotion, EASE } from '@/motion'
import type { Coverage } from '@/types'

const props = defineProps<{ coverage: Coverage[] }>()
const emit = defineEmits<{ select: [regionId: string] }>()

/** Ordem fixa das células dentro do módulo: 2 colunas × 3 linhas. */
const DOMAINS = [
  { key: 'population', label: 'população', has: (r: Coverage) => r.population_2022_available },
  { key: 'security', label: 'segurança', has: (r: Coverage) => r.security_years_with_data > 0 },
  { key: 'health', label: 'saúde', has: (r: Coverage) => r.health_facilities > 0 },
  { key: 'education', label: 'educação', has: (r: Coverage) => r.education_schools > 0 },
  { key: 'mobility', label: 'mobilidade', has: (r: Coverage) => r.mobility_bikeway_km > 0 },
  { key: 'weather', label: 'clima', has: (r: Coverage) => r.weather_days > 0 },
] as const

const CELL = 4
const GAP = 1
const MODULE_W = CELL * 2 + GAP
const MODULE_H = CELL * 3 + GAP * 2
const PITCH = MODULE_W + 4

const hovered = ref<string | null>(null)
const root = ref<SVGSVGElement | null>(null)

const modules = computed(() =>
  props.coverage.map((region, index) => ({
    id: region.region_id,
    name: region.region_name,
    x: index * PITCH,
    missing: DOMAINS.filter((domain) => !domain.has(region)).map((domain) => domain.label),
    cells: DOMAINS.map((domain, position) => ({
      key: domain.key,
      x: (position % 2) * (CELL + GAP),
      y: Math.floor(position / 2) * (CELL + GAP),
      filled: domain.has(region),
    })),
  })),
)

const width = computed(() => Math.max(modules.value.length * PITCH - 4, 1))

const summary = computed(() => {
  const complete = props.coverage.filter((region) => region.domains_with_data === 6).length
  return `Malha de cobertura: ${complete} das ${props.coverage.length} Regiões Administrativas têm dado publicado nos seis domínios.`
})

const hoveredModule = computed(
  () => modules.value.find((item) => item.id === hovered.value) ?? null,
)

// O painel é plotado célula a célula, a partir do centro — não aparece pronto.
watch(
  () => modules.value.length,
  (count) => {
    if (count === 0 || prefersReducedMotion()) return
    requestAnimationFrame(() => {
      const cells = root.value?.querySelectorAll('[data-cell]')
      if (!cells?.length) return
      gsap.fromTo(
        cells,
        { opacity: 0, scale: 0.4, transformOrigin: 'center' },
        {
          opacity: 1,
          scale: 1,
          duration: 0.5,
          ease: EASE,
          stagger: { each: 0.004, from: 'center' },
        },
      )
    })
  },
  { immediate: true },
)
</script>

<template>
  <div v-if="modules.length" class="relative">
    <svg
      ref="root"
      :viewBox="`0 0 ${width} ${MODULE_H}`"
      :style="{ maxWidth: `${width}px` }"
      class="h-auto w-full"
      preserveAspectRatio="xMinYMid meet"
      role="img"
      :aria-label="summary"
      @mouseleave="hovered = null"
    >
      <g
        v-for="item in modules"
        :key="item.id"
        :transform="`translate(${item.x} 0)`"
        class="cursor-pointer"
        @mouseenter="hovered = item.id"
        @click="emit('select', item.id)"
      >
        <!-- Alvo de mouse do módulo inteiro: as células são pequenas demais. -->
        <rect :width="MODULE_W" :height="MODULE_H" fill="transparent" />
        <rect
          v-for="cell in item.cells"
          :key="cell.key"
          data-cell
          :x="cell.x"
          :y="cell.y"
          :width="CELL"
          :height="CELL"
          :fill="cell.filled ? (hovered === item.id ? '#FF006A' : '#FFFFFF') : 'transparent'"
          :fill-opacity="cell.filled ? (hovered === item.id ? 1 : 0.8) : 0"
          :stroke="cell.filled ? 'none' : '#3A1C5E'"
          stroke-width="1"
          class="transition-[fill,fill-opacity] duration-150"
        />
      </g>
    </svg>

    <div
      v-if="hoveredModule"
      class="pointer-events-none absolute left-0 top-[18px] z-50 whitespace-nowrap border
             border-line bg-elevated px-2.5 py-1.5 font-mono text-[10px] uppercase
             tracking-[0.1em] text-muted"
      :style="{ transform: `translateX(${Math.min(hoveredModule.x, width - 180)}px)` }"
    >
      <span class="text-ink">{{ hoveredModule.name }}</span>
      <span v-if="hoveredModule.missing.length" class="text-warn">
        · sem {{ hoveredModule.missing.join(', ') }}
      </span>
      <span v-else> · seis domínios</span>
    </div>
  </div>
</template>
