<script setup lang="ts">
/** Ranking horizontal. Linhas sem valor aparecem como "sem dado", não como zero. */
import { computed } from 'vue'
import { EMPTY } from '@/format'

const props = withDefaults(
  defineProps<{
    items: { id: string; label: string; value: number | null; hint?: string }[]
    color?: string
    formatValue?: (value: number) => string
    selectedId?: string | null
    limit?: number
  }>(),
  {
    color: '#5EE6C5',
    formatValue: (value: number) => value.toLocaleString('pt-BR'),
    selectedId: null,
    limit: 12,
  },
)

const emit = defineEmits<{ select: [id: string] }>()

const ranked = computed(() => {
  const withValue = props.items.filter((item) => item.value !== null)
  const max = Math.max(...withValue.map((item) => item.value as number), 0)
  return withValue
    .sort((a, b) => (b.value as number) - (a.value as number))
    .slice(0, props.limit)
    .map((item) => ({ ...item, ratio: max > 0 ? (item.value as number) / max : 0 }))
})

const missing = computed(() => props.items.filter((item) => item.value === null))
</script>

<template>
  <div>
    <ul class="space-y-1">
      <li v-for="(item, index) in ranked" :key="item.id">
        <button
          type="button"
          class="group grid w-full grid-cols-[1.4rem_minmax(0,1fr)_auto] items-center gap-3 rounded-lg
                 px-2 py-1.5 text-left transition-colors hover:bg-elevated
                 focus:outline-none focus-visible:ring-1 focus-visible:ring-line"
          :class="selectedId === item.id ? 'bg-elevated' : ''"
          @click="emit('select', item.id)"
        >
          <span class="tnum text-[11px] text-faint">{{ index + 1 }}</span>
          <span class="min-w-0">
            <span class="flex items-baseline justify-between gap-3">
              <span class="truncate text-sm text-ink">{{ item.label }}</span>
              <span v-if="item.hint" class="shrink-0 text-[11px] text-faint">{{ item.hint }}</span>
            </span>
            <span class="mt-1 block h-1.5 overflow-hidden rounded-full bg-elevated">
              <span
                class="block h-full rounded-full transition-[width] duration-500"
                :style="{ width: `${Math.max(item.ratio * 100, 2)}%`, background: color }"
              />
            </span>
          </span>
          <span class="tnum text-sm text-muted group-hover:text-ink">
            {{ formatValue(item.value as number) }}
          </span>
        </button>
      </li>
    </ul>

    <p v-if="missing.length" class="mt-3 text-[11px] text-faint">
      {{ missing.length }}
      {{ missing.length === 1 ? 'região sem dado publicado' : 'regiões sem dado publicado' }}
      ({{ EMPTY }}): {{ missing.map((item) => item.label).join(', ') }}
    </p>
  </div>
</template>
