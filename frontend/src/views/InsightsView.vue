<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api'
import { DOMAIN_COLORS, DOMAIN_LABELS } from '@/format'
import type { Insight, Source } from '@/types'
import LoadState from '@/components/LoadState.vue'
import { useIsPhone } from '@/composables/useMedia'

/** No celular a metodologia começa recolhida: o achado primeiro, o método a um toque. */
const isPhone = useIsPhone()

const loading = ref(true)
const error = ref<string | null>(null)
const insights = ref<Insight[]>([])
const sources = ref<Source[]>([])
const activeDomain = ref<string>('todos')

const domains = computed(() => [
  'todos',
  ...[...new Set(insights.value.map((insight) => insight.domain))],
])

const visible = computed(() =>
  activeDomain.value === 'todos'
    ? insights.value
    : insights.value.filter((insight) => insight.domain === activeDomain.value),
)

const sourcesById = computed(() => new Map(sources.value.map((source) => [source.source_id, source])))

function periodOf(insight: Insight): string {
  if (!insight.period_start) return ''
  return insight.period_start === insight.period_end
    ? String(insight.period_start)
    : `${insight.period_start}–${insight.period_end}`
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const [insightList, sourceList] = await Promise.all([api.insights(), api.sources()])
    insights.value = insightList
    sources.value = sourceList
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-8">
    <header>
      <h1
        v-reveal
        class="font-display text-[2.5rem] font-bold uppercase leading-[0.95] tracking-tight sm:text-[3.5rem]"
        style="font-stretch: 118%"
      >
        Insights
      </h1>
      <div v-reveal.rule class="mt-5 h-px w-full bg-line" />
      <p v-reveal class="mt-5 max-w-2xl text-sm leading-relaxed text-muted">
        Achados calculados a partir dos dados — nenhum texto foi redigido à mão. Cada um mostra o
        período, o método de cálculo, a fonte e a limitação conhecida.
      </p>
    </header>

    <div
      v-reveal
      class="border-l-2 border-accent bg-elevated/50 px-4 py-3 text-xs leading-relaxed text-muted"
    >
      <strong class="text-ink">Sobre a leitura destes números.</strong>
      Todos descrevem o que foi <em>registrado</em>, não o que necessariamente aconteceu. Onde duas
      séries se movem juntas, isso é associação estatística:
      <strong class="text-ink">correlação não implica causalidade</strong>. Nenhum achado aqui
      afirma causa.
    </div>

    <LoadState :loading="loading" :error="error" :empty="!loading && !error && insights.length === 0" @retry="load">
      <div class="rail" role="tablist" aria-label="Filtrar por domínio">
        <button
          v-for="domain in domains"
          :key="domain"
          type="button"
          role="tab"
          :aria-selected="activeDomain === domain"
          class="min-h-[40px] border px-3 py-2 font-mono text-[11px] uppercase tracking-[0.1em] transition-colors
                 sm:min-h-0 sm:py-1.5 sm:text-[10px]"
          :class="
            activeDomain === domain
              ? 'border-transparent bg-elevated text-ink'
              : 'border-line text-muted hover:text-ink'
          "
          :style="
            activeDomain === domain && domain !== 'todos'
              ? { borderColor: DOMAIN_COLORS[domain], color: DOMAIN_COLORS[domain] }
              : undefined
          "
          @click="activeDomain = domain"
        >
          {{ domain === 'todos' ? 'Todos' : DOMAIN_LABELS[domain] ?? domain }}
        </button>
      </div>

      <div class="mt-6 grid grid-cols-1 gap-4 sm:gap-5 lg:grid-cols-2">
        <article
          v-for="insight in visible"
          :key="insight.insight_id"
          v-reveal
          class="card card-pad"
        >
          <div class="flex flex-wrap items-center gap-2">
            <span
              class="chip"
              :style="{ color: DOMAIN_COLORS[insight.domain], borderColor: `${DOMAIN_COLORS[insight.domain]}40` }"
            >
              {{ DOMAIN_LABELS[insight.domain] ?? insight.domain }}
            </span>
            <span v-if="periodOf(insight)" class="chip">{{ periodOf(insight) }}</span>
          </div>

          <h2 class="mt-4 font-display text-lg font-semibold leading-snug">{{ insight.title }}</h2>
          <p class="mt-3 text-[15px] leading-relaxed text-ink/90">{{ insight.finding }}</p>

          <!-- A limitação fica sempre à vista: ler o achado sem ela é ler errado. -->
          <p v-if="insight.caveat" class="mt-4 border-l-2 border-warn/60 pl-3 text-xs leading-relaxed text-warn/90">
            <span class="label mr-1 text-warn">Limitação</span>
            {{ insight.caveat }}
          </p>

          <details class="group mt-4 border-t border-line pt-1" :open="!isPhone">
            <summary
              class="flex min-h-[44px] cursor-pointer list-none items-center justify-between font-mono text-[11px]
                     uppercase tracking-[0.12em] text-faint sm:hidden [&::-webkit-details-marker]:hidden"
            >
              Metodologia e fonte
              <svg viewBox="0 0 24 24" class="h-4 w-4 transition-transform group-open:rotate-180" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>
            </summary>
          <dl class="space-y-3 pb-1 pt-3 text-xs leading-relaxed">
            <div>
              <dt class="label">Metodologia</dt>
              <dd class="mt-1 text-muted">{{ insight.method }}</dd>
            </div>
            <div>
              <dt class="label">Fonte</dt>
              <dd class="mt-1 text-muted">
                <a
                  v-if="sourcesById.get(insight.source_id)"
                  :href="sourcesById.get(insight.source_id)!.url"
                  target="_blank"
                  rel="noopener"
                  class="link-underline"
                >
                  {{ sourcesById.get(insight.source_id)!.organization }} —
                  {{ sourcesById.get(insight.source_id)!.source_name }}
                </a>
                <span v-else>{{ insight.source_id }}</span>
              </dd>
            </div>
          </dl>
          </details>
        </article>
      </div>
    </LoadState>
  </div>
</template>
