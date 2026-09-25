<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api'
import { DOMAIN_COLORS, DOMAIN_LABELS } from '@/format'
import type { Insight, Source } from '@/types'
import LoadState from '@/components/LoadState.vue'

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
      <div class="rail">
        <button
          v-for="domain in domains"
          :key="domain"
          type="button"
          class="border px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.1em] transition-colors"
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

      <div class="mt-6 grid gap-5 lg:grid-cols-2">
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

          <dl class="mt-5 space-y-3 border-t border-line pt-4 text-xs leading-relaxed">
            <div>
              <dt class="label">Metodologia</dt>
              <dd class="mt-1 text-muted">{{ insight.method }}</dd>
            </div>
            <div v-if="insight.caveat">
              <dt class="label">Limitação</dt>
              <dd class="mt-1 text-warn/85">{{ insight.caveat }}</dd>
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
        </article>
      </div>
    </LoadState>
  </div>
</template>
