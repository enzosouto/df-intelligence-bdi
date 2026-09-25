<script setup lang="ts">
/**
 * Ranking horizontal. Linha sem valor nunca vira zero: sai do ranking e é
 * listada por nome embaixo, para que a ausência tenha endereço.
 *
 * As barras crescem da esquerda em cascata a cada troca de métrica — a mesma
 * gramática de movimento das réguas do resto da página. Ver a cascata é ver a
 * ordem mudar; um corte seco esconderia que a lista foi reordenada.
 */
import { computed, nextTick, ref, watch } from 'vue'
import { gsap } from 'gsap'
import { EMPTY } from '@/format'
import { EASE, prefersReducedMotion } from '@/motion'

const props = withDefaults(
  defineProps<{
    items: { id: string; label: string; value: number | null; hint?: string }[]
    color?: string
    formatValue?: (value: number) => string
    selectedId?: string | null
    limit?: number
  }>(),
  {
    color: '#FFFFFF',
    formatValue: (value: number) => value.toLocaleString('pt-BR'),
    selectedId: null,
    limit: 12,
  },
)

const emit = defineEmits<{ select: [id: string] }>()

const root = ref<HTMLElement | null>(null)

const ranked = computed(() => {
  const withValue = props.items.filter((item) => item.value !== null)
  const max = Math.max(...withValue.map((item) => item.value as number), 0)
  return withValue
    .sort((a, b) => (b.value as number) - (a.value as number))
    .slice(0, props.limit)
    .map((item) => ({ ...item, ratio: max > 0 ? (item.value as number) / max : 0 }))
})

const missing = computed(() => props.items.filter((item) => item.value === null))

watch(
  ranked,
  async () => {
    if (prefersReducedMotion()) return
    await nextTick()
    const bars = root.value?.querySelectorAll<HTMLElement>('[data-bar]')
    if (!bars?.length) return
    gsap.fromTo(
      bars,
      { scaleX: 0 },
      {
        scaleX: 1,
        duration: 0.55,
        ease: EASE,
        transformOrigin: 'left center',
        stagger: 0.025,
      },
    )
  },
  { immediate: true },
)
</script>

<template>
  <div ref="root">
    <ul>
      <li v-for="(item, index) in ranked" :key="item.id" class="border-b border-line/60 last:border-0">
        <button
          type="button"
          class="group grid w-full grid-cols-[1.6rem_minmax(0,1fr)_auto] items-center gap-3
                 py-2 text-left transition-colors hover:bg-elevated"
          :class="selectedId === item.id ? 'bg-elevated' : ''"
          @click="emit('select', item.id)"
        >
          <span class="font-mono text-[10px] text-accent tnum">
            {{ String(index + 1).padStart(2, '0') }}
          </span>
          <span class="min-w-0">
            <span class="flex items-baseline justify-between gap-3">
              <span class="truncate text-[13px] text-ink">{{ item.label }}</span>
              <span v-if="item.hint" class="shrink-0 font-mono text-[10px] text-faint">
                {{ item.hint }}
              </span>
            </span>
            <span class="mt-1.5 block h-[3px] bg-elevated">
              <span
                data-bar
                class="block h-full"
                :style="{ width: `${Math.max(item.ratio * 100, 1.5)}%`, background: color }"
              />
            </span>
          </span>
          <span class="font-mono text-[12px] text-muted tnum group-hover:text-ink">
            {{ formatValue(item.value as number) }}
          </span>
        </button>
      </li>
    </ul>

    <p v-if="missing.length" class="mt-4 border-l-2 border-line pl-3 text-[11px] leading-relaxed text-faint">
      <span class="label mr-1.5">Sem dado ({{ EMPTY }})</span>
      {{ missing.map((item) => item.label).join(' · ') }}
    </p>
  </div>
</template>
