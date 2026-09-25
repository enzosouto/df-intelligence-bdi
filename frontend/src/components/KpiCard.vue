<script setup lang="ts">
/**
 * Medida única, em célula da grade.
 *
 * Aceita `count` quando o valor é numérico — aí o número corre até ele, e a
 * leitura do dígito final é o fim da animação, não um enfeite. Valor textual
 * (data, rótulo) entra por `value` e não anima: não há o que contar.
 */
import { onMounted, ref, watch } from 'vue'
import { countTo } from '@/motion'

const props = withDefaults(
  defineProps<{
    label: string
    value?: string
    count?: number | null
    format?: (value: number) => string
    hint?: string
    accent?: string
    loading?: boolean
  }>(),
  { value: '—', count: null, format: (value: number) => String(Math.round(value)) },
)

const numberEl = ref<HTMLElement | null>(null)

function run() {
  if (props.count === null || props.count === undefined || !numberEl.value) return
  countTo(numberEl.value, props.count, props.format)
}

onMounted(run)
watch(() => props.count, run)
</script>

<template>
  <!-- Sem borda própria: os KPIs vivem numa grade que já desenha as réguas
       entre as células com `gap-px`. Borda aqui viraria linha dupla. -->
  <div v-reveal class="card-pad relative bg-surface">
    <span
      v-if="accent"
      class="absolute left-0 top-0 h-full w-[3px]"
      :style="{ background: accent }"
      aria-hidden="true"
    />
    <p class="label">{{ label }}</p>
    <div v-if="loading" class="skeleton mt-3 h-9 w-28" />
    <!-- Texto (uma data, um rótulo) não cabe na escala de um número: na
         largura de uma coluna, "24 de setembro de 2026" vira três linhas. -->
    <p
      v-else
      ref="numberEl"
      class="mt-3"
      :class="
        count === null || count === undefined
          ? 'font-display text-xl font-semibold leading-tight'
          : 'metric'
      "
      :style="accent ? { color: accent } : undefined"
    >
      {{ count === null || count === undefined ? value : format(count) }}
    </p>
    <p v-if="hint" class="mt-3 font-mono text-[11px] leading-relaxed text-faint">{{ hint }}</p>
  </div>
</template>
