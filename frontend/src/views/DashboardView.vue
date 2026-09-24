<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import { dec, fullDate, monthLabel, num, pct, short, temperature } from '@/format'
import type { Overview, PopulationPoint, RegionFeature, RegionIndicators, SecurityPoint, WeatherPoint } from '@/types'
import KpiCard from '@/components/KpiCard.vue'
import LineChart from '@/components/LineChart.vue'
import type { Series } from '@/components/chart'
import LoadState from '@/components/LoadState.vue'
import RankBars from '@/components/RankBars.vue'
import RegionMap from '@/components/RegionMap.vue'
import DataNotice from '@/components/DataNotice.vue'

const router = useRouter()

const loading = ref(true)
const error = ref<string | null>(null)

const overview = ref<Overview | null>(null)
const features = ref<RegionFeature[]>([])
const indicators = ref<RegionIndicators[]>([])
const populationDF = ref<PopulationPoint[]>([])
const securitySeries = ref<SecurityPoint[]>([])
const weatherSeries = ref<WeatherPoint[]>([])

/** Métricas que o mapa sabe pintar. Cada uma carrega sua ressalva. */
const METRICS = [
  {
    key: 'population',
    label: 'População',
    color: '#5EE6C5',
    of: (region: RegionIndicators) => region.population_2022,
    format: (value: number | null) => (value === null ? '—' : `${num(value)} hab.`),
    note: 'Censo 2022 (IBGE). Arapoanga e Água Quente não têm valor publicado — o IBGE conta a população delas dentro das RAs de origem.',
  },
  {
    key: 'density',
    label: 'Densidade',
    color: '#5EE6C5',
    of: (region: RegionIndicators) => region.density_2022_per_km2,
    format: (value: number | null) => (value === null ? '—' : `${dec(value, 1)} hab/km²`),
    note: 'A área inclui zonas rurais e de preservação dentro do limite da RA, o que reduz a densidade das regiões mais extensas.',
  },
  {
    key: 'crime_rate',
    label: 'Crimes / 10 mil hab.',
    color: '#FF6B81',
    of: (region: RegionIndicators) => region.crimes_per_10k,
    format: (value: number | null) => (value === null ? '—' : dec(value, 1)),
    note: 'Último ano completo publicado para cada RA, sobre a população do Censo 2022. Regiões com muito fluxo de não residentes (áreas comerciais e industriais) têm taxa inflada, porque o denominador conta só quem mora ali.',
  },
  {
    key: 'cvli',
    label: 'CVLI / 100 mil hab.',
    color: '#FF6B81',
    of: (region: RegionIndicators) => region.cvli_per_100k,
    format: (value: number | null) => (value === null ? '—' : dec(value, 1)),
    note: 'Crimes Violentos Letais Intencionais: homicídio, latrocínio e lesão corporal seguida de morte.',
  },
  {
    key: 'bikeway',
    label: 'Ciclovia / 10 mil hab.',
    color: '#FF8A4C',
    of: (region: RegionIndicators) => region.bikeway_km_per_10k,
    format: (value: number | null) => (value === null ? '—' : `${dec(value, 1)} km`),
    note: 'Km de ciclovia, ciclofaixa e calçada compartilhada dentro da RA (IDE-DF), por 10 mil habitantes do Censo 2022. Mede extensão instalada, não uso nem qualidade.',
  },
  {
    key: 'health',
    label: 'Saúde / 10 mil hab.',
    color: '#4CC2FF',
    of: (region: RegionIndicators) => region.health_facilities_per_10k,
    format: (value: number | null) => (value === null ? '—' : dec(value, 1)),
    note: 'Estabelecimentos cadastrados no CNES. É oferta instalada, não produção de atendimentos — e a maioria dos registros são clínicas e consultórios privados.',
  },
  {
    key: 'temperature',
    label: 'Temperatura média',
    color: '#A98BFF',
    of: (region: RegionIndicators) => region.temp_mean_c,
    format: (value: number | null) => temperature(value),
    note: 'Reanálise ERA5 via Open-Meteo — fonte externa, não medição do INMET. A resolução do modelo é maior que uma RA, então a variação entre regiões é pequena.',
  },
] as const

const metricKey = ref<(typeof METRICS)[number]['key']>('population')
const metric = computed(() => METRICS.find((item) => item.key === metricKey.value)!)
const hoveredRegion = ref<string | null>(null)

const indicatorsById = computed(
  () => new Map(indicators.value.map((region) => [region.region_id, region])),
)

function metricValueOf(feature: RegionFeature): number | null {
  const region = indicatorsById.value.get(feature.properties.region_id)
  return region ? metric.value.of(region) : null
}

const ranking = computed(() =>
  indicators.value.map((region) => ({
    id: region.region_id,
    label: region.region_name,
    value: metric.value.of(region),
    hint: metricKey.value === 'crime_rate' ? String(region.security_reference_year ?? '') : undefined,
  })),
)

/** Série do DF: as lacunas do IBGE viram buraco na linha, não linha reta. */
const populationChart = computed<Series[]>(() => {
  if (populationDF.value.length === 0) return []
  const years = populationDF.value.map((point) => point.reference_year)
  const byYear = new Map(populationDF.value.map((point) => [point.reference_year, point.population]))
  const allYears: number[] = []
  for (let year = Math.min(...years); year <= Math.max(...years); year += 1) allYears.push(year)
  return [
    {
      key: 'pop',
      label: 'População do DF',
      color: '#5EE6C5',
      points: allYears.map((year) => ({ x: String(year), y: byYear.get(year) ?? null })),
    },
  ]
})

const securityChart = computed<Series[]>(() => {
  const crimes = securitySeries.value.filter((point) => point.metric_type === 'CRIME')
  const months = [...new Set(crimes.map((point) => point.reference_month_start))].sort()
  const categories = [
    { code: 'CVLI', label: 'CVLI', color: '#FF6B81' },
    { code: 'CCP', label: 'Crimes contra o patrimônio', color: '#F5A524' },
    { code: 'OUTROS', label: 'Outros crimes', color: '#4CC2FF' },
  ]
  return categories.map((category) => {
    const byMonth = new Map(
      crimes
        .filter((point) => point.category_code === category.code)
        .map((point) => [point.reference_month_start, point.occurrences]),
    )
    return {
      key: category.code,
      label: category.label,
      color: category.color,
      points: months.map((month) => ({ x: month, y: byMonth.get(month) ?? null })),
    }
  })
})

const weatherChart = computed<Series[]>(() => {
  const points = weatherSeries.value
  return [
    {
      key: 'tmax',
      label: 'Máxima média',
      color: '#F5A524',
      points: points.map((point) => ({
        x: point.reference_month_start,
        y: point.temp_max_avg_c,
        partial: point.days_observed < 28,
      })),
    },
    {
      key: 'tmin',
      label: 'Mínima média',
      color: '#A98BFF',
      points: points.map((point) => ({
        x: point.reference_month_start,
        y: point.temp_min_avg_c,
        partial: point.days_observed < 28,
      })),
    },
  ]
})

const rainChart = computed<Series[]>(() => [
  {
    key: 'rain',
    label: 'Precipitação mensal (média das RAs)',
    color: '#4CC2FF',
    points: weatherSeries.value.map((point) => ({
      x: point.reference_month_start,
      y: point.precipitation_mm,
      partial: point.days_observed < 28,
    })),
  },
])

const totals = computed(() => {
  const list = indicators.value
  return {
    crimes: list.reduce((sum, region) => sum + (region.crimes_total ?? 0), 0),
    facilities: list.reduce((sum, region) => sum + region.health_facilities, 0),
    withCrimeData: list.filter((region) => region.security_reference_year !== null).length,
  }
})

async function load() {
  loading.value = true
  error.value = null
  try {
    const [overviewData, geo, indicatorList, populationSeries, security, weather] = await Promise.all([
      api.overview(),
      api.regionsGeoJSON(),
      api.indicators(),
      api.population({ scope: 'df' }),
      api.securitySummary({ year_from: 2018 }),
      api.weatherSummary({ year_from: 2022 }),
    ])
    overview.value = overviewData
    features.value = geo.features
    indicators.value = indicatorList
    populationDF.value = populationSeries
    securitySeries.value = security
    weatherSeries.value = weather
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
    <!-- Cabeçalho -->
    <section class="animate-fade-up">
      <h1 class="font-display text-4xl font-bold tracking-tight sm:text-5xl">
        Brasília através dos dados.
      </h1>
      <p class="mt-3 max-w-2xl text-sm leading-relaxed text-muted">
        Dados públicos de população, segurança, saúde, educação, mobilidade e clima consolidados
        por Região Administrativa — com a cobertura real de cada fonte à mostra, não escondida.
      </p>
    </section>

    <LoadState :loading="loading" :error="error" @retry="load">
      <!-- KPIs -->
      <section class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="População do DF"
          :value="short(overview?.population_df_latest)"
          :hint="
            overview
              ? `${overview.population_df_is_projection ? 'Projeção' : 'Censo'} IBGE ${overview.population_df_latest_year} · ${num(overview.population_df_latest)} habitantes`
              : ''
          "
          accent="#5EE6C5"
        />
        <KpiCard
          label="Regiões Administrativas"
          :value="String(overview?.regions_total ?? '—')"
          :hint="`${overview?.regions_with_all_domains ?? 0} com dados nos quatro domínios`"
        />
        <KpiCard
          label="Indicadores monitorados"
          :value="String(overview?.indicators_monitored ?? '—')"
          :hint="`${overview?.sources_total ?? 0} fontes catalogadas · ${overview?.government_sources_total ?? 0} do GDF`"
        />
        <KpiCard
          label="Última atualização"
          :value="overview?.data_last_updated_at ? fullDate(overview.data_last_updated_at) : '—'"
          :hint="
            overview?.security_last_month
              ? `Segurança até ${monthLabel(overview.security_last_month)} · clima até ${fullDate(overview.weather_last_day)}`
              : ''
          "
        />
      </section>

      <!-- Mapa + ranking -->
      <section class="mt-10 grid gap-6 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
        <div class="card card-pad">
          <div class="mb-5 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 class="font-display text-lg font-semibold">Mapa do Distrito Federal</h2>
              <p class="mt-1 text-xs text-faint">
                35 Regiões Administrativas · clique para abrir o detalhe
              </p>
            </div>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="item in METRICS"
                :key="item.key"
                type="button"
                class="rounded-lg border px-2.5 py-1.5 text-[11px] transition-colors"
                :class="
                  metricKey === item.key
                    ? 'border-transparent text-base'
                    : 'border-line text-muted hover:border-line hover:text-ink'
                "
                :style="metricKey === item.key ? { background: item.color } : undefined"
                @click="metricKey = item.key"
              >
                {{ item.label }}
              </button>
            </div>
          </div>

          <RegionMap
            :features="features"
            :metric-of="metricValueOf"
            :format-value="metric.format"
            :color="metric.color"
            :selected-id="hoveredRegion"
            :metric-label="metric.label"
            @select="router.push(`/regiao/${$event}`)"
            @hover="hoveredRegion = $event"
          />

          <DataNotice class="mt-5">{{ metric.note }}</DataNotice>
        </div>

        <div class="card card-pad">
          <h2 class="font-display text-lg font-semibold">Ranking · {{ metric.label }}</h2>
          <p class="mb-4 mt-1 text-xs text-faint">Maiores valores entre as 35 RAs</p>
          <RankBars
            :items="ranking"
            :color="metric.color"
            :format-value="(value) => metric.format(value)"
            :selected-id="hoveredRegion"
            :limit="14"
            @select="router.push(`/regiao/${$event}`)"
          />
        </div>
      </section>

      <!-- Cards de domínio -->
      <section class="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div class="card card-pad">
          <p class="label" style="color: #5ee6c5">População</p>
          <p class="metric mt-2">{{ short(overview?.population_df_latest) }}</p>
          <p class="mt-2 text-xs text-faint">
            Habitantes no DF ({{ overview?.population_df_latest_year }}). Por RA, só o Censo mede.
          </p>
        </div>
        <div class="card card-pad">
          <p class="label" style="color: #ff6b81">Segurança</p>
          <p class="metric mt-2">{{ short(totals.crimes) }}</p>
          <p class="mt-2 text-xs text-faint">
            Crimes registrados no último ano completo de cada uma das
            {{ totals.withCrimeData }} RAs com publicação.
          </p>
        </div>
        <div class="card card-pad">
          <p class="label" style="color: #4cc2ff">Saúde</p>
          <p class="metric mt-2">{{ num(totals.facilities) }}</p>
          <p class="mt-2 text-xs text-faint">
            Estabelecimentos do CNES localizados em uma RA. Infraestrutura, não atendimentos.
          </p>
        </div>
        <div class="card card-pad">
          <p class="label" style="color: #a98bff">Clima</p>
          <p class="metric mt-2">
            {{ weatherSeries.length ? temperature(weatherSeries[weatherSeries.length - 1].temp_mean_c) : '—' }}
          </p>
          <p class="mt-2 text-xs text-faint">
            Temperatura média do último mês observado (ERA5/Open-Meteo).
          </p>
        </div>
      </section>

      <!-- Séries temporais -->
      <section class="mt-10 grid gap-6 lg:grid-cols-2">
        <div class="card card-pad">
          <h2 class="font-display text-lg font-semibold">Evolução da população do DF</h2>
          <p class="mb-5 mt-1 text-xs text-faint">
            Série do IBGE, {{ populationDF[0]?.reference_year }}–{{
              populationDF[populationDF.length - 1]?.reference_year
            }}
            ·
            {{
              populationDF.length
                ? pct(
                    (100 *
                      (populationDF[populationDF.length - 1].population - populationDF[0].population)) /
                      populationDF[0].population,
                  )
                : ''
            }}
            no período
          </p>
          <LineChart
            :series="populationChart"
            :format-value="(value) => short(value)"
            :y-zero="false"
          />
          <DataNotice class="mt-4">
            A linha tem buracos porque o IBGE não publica estimativa em anos de Censo e de revisão
            metodológica. Interpolar esses anos seria inventar dado.
          </DataNotice>
        </div>

        <div class="card card-pad">
          <h2 class="font-display text-lg font-semibold">Crimes registrados por mês</h2>
          <p class="mb-5 mt-1 text-xs text-faint">
            Soma das RAs que publicaram cada mês · SSP-DF, a partir de 2018
          </p>
          <LineChart
            :series="securityChart"
            :format-value="(value) => short(value)"
            :format-x="monthLabel"
            :area="false"
          />
          <DataNotice tone="warn" class="mt-4">
            A cobertura da SSP-DF varia por RA e por ano. Quedas na linha podem refletir RAs que
            deixaram de publicar, e não redução de ocorrências — confira em Fontes &amp; Qualidade.
          </DataNotice>
        </div>

        <div class="card card-pad">
          <h2 class="font-display text-lg font-semibold">Temperatura média mensal</h2>
          <p class="mb-5 mt-1 text-xs text-faint">Média das 35 RAs · ERA5/Open-Meteo</p>
          <LineChart
            :series="weatherChart"
            :format-value="(value) => `${dec(value, 0)}°`"
            :format-x="monthLabel"
            :area="false"
            :y-zero="false"
          />
        </div>

        <div class="card card-pad">
          <h2 class="font-display text-lg font-semibold">Precipitação mensal</h2>
          <p class="mb-5 mt-1 text-xs text-faint">
            A seca de maio a setembro é a marca climática do Planalto Central
          </p>
          <LineChart
            :series="rainChart"
            :format-value="(value) => `${dec(value, 0)} mm`"
            :format-x="monthLabel"
          />
          <DataNotice class="mt-4">
            Open-Meteo/ERA5 é uma fonte externa e não governamental: são valores de modelo de
            reanálise interpolados, não leitura de estação do INMET.
          </DataNotice>
        </div>
      </section>
    </LoadState>
  </div>
</template>
