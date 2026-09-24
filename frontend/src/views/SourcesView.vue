<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '@/api'
import { dateTime, num } from '@/format'
import type { Coverage, Indicator, PipelineStatus, Source } from '@/types'
import LoadState from '@/components/LoadState.vue'

const loading = ref(true)
const error = ref<string | null>(null)
const sources = ref<Source[]>([])
const coverage = ref<Coverage[]>([])
const pipeline = ref<PipelineStatus[]>([])
const catalog = ref<Indicator[]>([])

const coverageSummary = computed(() => {
  const missing2024 = coverage.value.filter((item) => item.security_missing_years.includes(2024))
  const withoutPopulation = coverage.value.filter((item) => !item.population_2022_available)
  return {
    complete: coverage.value.filter((item) => item.has_all_domains).length,
    total: coverage.value.length,
    missing2024,
    withoutPopulation,
  }
})

async function load() {
  loading.value = true
  error.value = null
  try {
    const [sourceList, coverageList, pipelineList, catalogList] = await Promise.all([
      api.sources(),
      api.coverage(),
      api.pipeline(),
      api.indicatorCatalog(),
    ])
    sources.value = sourceList
    coverage.value = coverageList
    pipeline.value = pipelineList
    catalog.value = catalogList
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-10">
    <header class="animate-fade-up">
      <h1 class="font-display text-4xl font-bold tracking-tight sm:text-5xl">
        Fontes &amp; Qualidade
      </h1>
      <p class="mt-3 max-w-2xl text-sm leading-relaxed text-muted">
        De onde vem cada número, com que frequência é atualizado e — principalmente — o que está
        faltando. Lacuna de dado nunca é exibida como zero neste produto.
      </p>
    </header>

    <LoadState :loading="loading" :error="error" @retry="load">
      <!-- Fontes -->
      <section>
        <h2 class="font-display text-xl font-semibold">Fontes de dados</h2>
        <div class="mt-5 grid gap-4 lg:grid-cols-2">
          <article v-for="source in sources" :key="source.source_id" class="card card-pad">
            <div class="flex flex-wrap items-center gap-2">
              <span
                class="chip"
                :class="source.is_df_government ? 'text-population' : 'text-muted'"
              >
                {{ source.is_df_government ? 'Governo do DF' : 'Federal / externa' }}
              </span>
              <span class="chip">{{ source.update_frequency }}</span>
              <span class="chip">{{ source.temporal_coverage }}</span>
            </div>

            <h3 class="mt-4 font-display text-base font-semibold">{{ source.source_name }}</h3>
            <p class="mt-1 text-xs text-muted">{{ source.organization }}</p>

            <dl class="mt-4 space-y-2 text-xs">
              <div class="flex gap-2">
                <dt class="w-28 shrink-0 text-faint">Acesso</dt>
                <dd class="text-muted">{{ source.access_type }}</dd>
              </div>
              <div class="flex gap-2">
                <dt class="w-28 shrink-0 text-faint">Granularidade</dt>
                <dd class="text-muted">{{ source.granularity }}</dd>
              </div>
              <div class="flex gap-2">
                <dt class="w-28 shrink-0 text-faint">Endpoint</dt>
                <dd class="min-w-0">
                  <a :href="source.url" target="_blank" rel="noopener" class="link-underline break-all text-muted">
                    {{ source.url }}
                  </a>
                </dd>
              </div>
            </dl>

            <p v-if="source.caveat" class="mt-4 border-t border-line pt-3 text-xs leading-relaxed text-warn/85">
              {{ source.caveat }}
            </p>
          </article>
        </div>
      </section>

      <!-- Cobertura -->
      <section>
        <h2 class="font-display text-xl font-semibold">Cobertura por região</h2>
        <p class="mt-1 text-xs text-faint">
          {{ coverageSummary.complete }} de {{ coverageSummary.total }} RAs têm dado nos quatro
          domínios.
        </p>

        <div class="mt-5 grid gap-4 lg:grid-cols-2">
          <div class="card card-pad">
            <p class="label text-warn">Segurança sem publicação em 2024</p>
            <p class="metric mt-2">{{ coverageSummary.missing2024.length }}</p>
            <p class="mt-3 text-xs leading-relaxed text-muted">
              Na página oficial da SSP-DF, os links de 2024 dessas RAs apontam para arquivos de
              outros anos. Como o ano é lido de dentro da planilha, e não do link, o pipeline não
              inventa o dado — ele registra a ausência.
            </p>
            <p class="mt-3 text-xs text-faint">
              {{ coverageSummary.missing2024.map((item) => item.region_name).join(', ') }}
            </p>
          </div>

          <div class="card card-pad">
            <p class="label text-warn">População sem publicação no Censo 2022</p>
            <p class="metric mt-2">{{ coverageSummary.withoutPopulation.length }}</p>
            <p class="mt-3 text-xs leading-relaxed text-muted">
              O IBGE não divulga esses subdistritos separadamente: a população deles está contada
              dentro das RAs de origem. A soma das 33 RAs publicadas bate exatamente com o total do
              DF no Censo 2022 — o que confirma que nada foi perdido nem contado duas vezes.
            </p>
            <p class="mt-3 text-xs text-faint">
              {{ coverageSummary.withoutPopulation.map((item) => item.region_name).join(', ') }}
            </p>
          </div>
        </div>

        <div class="card mt-4 overflow-x-auto">
          <table class="w-full min-w-[46rem] text-sm">
            <thead>
              <tr class="border-b border-line text-left">
                <th class="px-5 py-3 font-medium text-faint">Região</th>
                <th class="px-5 py-3 font-medium text-faint">Pop. 2022</th>
                <th class="px-5 py-3 font-medium text-faint">Pop. 2010</th>
                <th class="px-5 py-3 font-medium text-faint">Segurança</th>
                <th class="px-5 py-3 font-medium text-faint">Anos ausentes</th>
                <th class="px-5 py-3 font-medium text-faint">Saúde</th>
                <th class="px-5 py-3 font-medium text-faint" title="Escolas no último censo · anos com matrícula completa">Educação</th>
                <th class="px-5 py-3 font-medium text-faint">Clima</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in coverage"
                :key="item.region_id"
                class="border-b border-line/60 last:border-0 hover:bg-elevated/50"
              >
                <td class="px-5 py-2.5">
                  <RouterLink :to="`/regiao/${item.region_id}`" class="hover:text-population">
                    {{ item.region_name }}
                  </RouterLink>
                </td>
                <td class="px-5 py-2.5">
                  <span :class="item.population_2022_available ? 'text-population' : 'text-warn'">
                    {{ item.population_2022_available ? 'sim' : 'não' }}
                  </span>
                </td>
                <td class="px-5 py-2.5 text-muted">
                  {{ item.population_2010_available ? 'sim' : 'não' }}
                </td>
                <td class="px-5 py-2.5 tnum text-muted">
                  {{ item.security_years_with_data }}/{{ item.security_years_expected }} anos
                </td>
                <td class="px-5 py-2.5 tnum text-xs text-warn/80">
                  {{ item.security_missing_years.join(', ') || '—' }}
                </td>
                <td class="px-5 py-2.5 tnum text-muted">{{ num(item.health_facilities) }}</td>
                <td class="px-5 py-2.5 tnum text-muted">
                  {{ num(item.education_schools) }}
                  <span class="text-faint">· {{ item.education_years_with_enrollment }} anos</span>
                </td>
                <td class="px-5 py-2.5 tnum text-muted">{{ num(item.weather_days) }} dias</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Pipeline -->
      <section>
        <h2 class="font-display text-xl font-semibold">Última execução do pipeline</h2>
        <div class="card mt-5 overflow-x-auto">
          <table class="w-full min-w-[42rem] text-sm">
            <thead>
              <tr class="border-b border-line text-left">
                <th class="px-5 py-3 font-medium text-faint">Fonte</th>
                <th class="px-5 py-3 font-medium text-faint">Status</th>
                <th class="px-5 py-3 font-medium text-faint">Concluída em</th>
                <th class="px-5 py-3 font-medium text-faint">Duração</th>
                <th class="px-5 py-3 font-medium text-faint">Linhas</th>
                <th class="px-5 py-3 font-medium text-faint">Requisições</th>
                <th class="px-5 py-3 font-medium text-faint">Alertas</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="run in pipeline" :key="run.source_key" class="border-b border-line/60 last:border-0">
                <td class="px-5 py-2.5">{{ run.source_key }}</td>
                <td class="px-5 py-2.5">
                  <span :class="run.status === 'SUCCESS' ? 'text-population' : 'text-security'">
                    {{ run.status }}
                  </span>
                </td>
                <td class="px-5 py-2.5 text-muted">{{ dateTime(run.finished_at) }}</td>
                <td class="px-5 py-2.5 tnum text-muted">{{ run.duration_seconds ?? '—' }}s</td>
                <td class="px-5 py-2.5 tnum text-muted">{{ num(run.rows_written) }}</td>
                <td class="px-5 py-2.5 tnum text-muted">{{ num(run.requests_made) }}</td>
                <td class="px-5 py-2.5 tnum">
                  <span v-if="run.failed_error_checks" class="text-security">
                    {{ run.failed_error_checks }} erro(s)
                  </span>
                  <span v-else-if="run.failed_warning_checks" class="text-warn">
                    {{ run.failed_warning_checks }} aviso(s)
                  </span>
                  <span v-else class="text-muted">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Dicionário de indicadores -->
      <section>
        <h2 class="font-display text-xl font-semibold">O que cada indicador mede</h2>
        <div class="mt-5 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <article v-for="indicator in catalog" :key="indicator.indicator_id" class="card card-pad">
            <p class="label">{{ indicator.unit }}</p>
            <h3 class="mt-2 font-display text-base font-semibold text-ink">{{ indicator.name }}</h3>
            <p class="mt-2 text-xs leading-relaxed text-muted">{{ indicator.description }}</p>
            <p class="mt-3 text-[11px] text-faint">{{ indicator.granularity }}</p>
            <p v-if="indicator.caveat" class="mt-3 border-t border-line pt-3 text-[11px] leading-relaxed text-warn/80">
              {{ indicator.caveat }}
            </p>
          </article>
        </div>
      </section>
    </LoadState>
  </div>
</template>
