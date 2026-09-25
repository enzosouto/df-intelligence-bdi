<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import { dec, fullDate, monthLabel, num, pct, short, temperature } from '@/format'
import type {
  EducationYear,
  MobilityRegion,
  Overview,
  PopulationPoint,
  RegionFeature,
  RegionIndicators,
  SecurityPoint,
  WeatherPoint,
} from '@/types'
import KpiCard from '@/components/KpiCard.vue'
import LineChart from '@/components/LineChart.vue'
import type { Series } from '@/components/chart'
import LoadState from '@/components/LoadState.vue'
import RankBars from '@/components/RankBars.vue'
import RegionMap from '@/components/RegionMap.vue'
import DataNotice from '@/components/DataNotice.vue'
import RegionPicker from '@/components/RegionPicker.vue'
import { useIsPhone } from '@/composables/useMedia'
import { hasFinePointer } from '@/motion'

const router = useRouter()
const isPhone = useIsPhone()
const fine = hasFinePointer()
/** No celular o ranking começa curto; a lista inteira fica a um toque. */
const showAllRanking = ref(false)
const rankingLimit = computed(() => (showAllRanking.value ? 35 : isPhone.value ? 8 : 14))

const loading = ref(true)
const error = ref<string | null>(null)

const overview = ref<Overview | null>(null)
const features = ref<RegionFeature[]>([])
const indicators = ref<RegionIndicators[]>([])
const populationDF = ref<PopulationPoint[]>([])
const securitySeries = ref<SecurityPoint[]>([])
const weatherSeries = ref<WeatherPoint[]>([])
const educationYears = ref<EducationYear[]>([])
const mobilityRegions = ref<MobilityRegion[]>([])

/** Métricas que o mapa sabe pintar. Cada uma carrega sua ressalva. */
const METRICS = [
  {
    key: 'population',
    label: 'População',
    color: '#FFFFFF',
    of: (region: RegionIndicators) => region.population_2022,
    format: (value: number | null) => (value === null ? '—' : `${num(value)} hab.`),
    note: 'Censo 2022 (IBGE). Arapoanga e Água Quente não têm valor publicado — o IBGE conta a população delas dentro das RAs de origem.',
  },
  {
    key: 'density',
    label: 'Densidade',
    color: '#FFFFFF',
    of: (region: RegionIndicators) => region.density_2022_per_km2,
    format: (value: number | null) => (value === null ? '—' : `${dec(value, 1)} hab/km²`),
    note: 'A área inclui zonas rurais e de preservação dentro do limite da RA, o que reduz a densidade das regiões mais extensas.',
  },
  {
    key: 'crime_rate',
    label: 'Crimes / 10 mil hab.',
    color: '#FF006A',
    of: (region: RegionIndicators) => region.crimes_per_10k,
    format: (value: number | null) => (value === null ? '—' : dec(value, 1)),
    note: 'Último ano completo publicado para cada RA, sobre a população do Censo 2022. Regiões com muito fluxo de não residentes (áreas comerciais e industriais) têm taxa inflada, porque o denominador conta só quem mora ali.',
  },
  {
    key: 'cvli',
    label: 'CVLI / 100 mil hab.',
    color: '#FF006A',
    of: (region: RegionIndicators) => region.cvli_per_100k,
    format: (value: number | null) => (value === null ? '—' : dec(value, 1)),
    note: 'Crimes Violentos Letais Intencionais: homicídio, latrocínio e lesão corporal seguida de morte.',
  },
  {
    key: 'bikeway',
    label: 'Ciclovia / 10 mil hab.',
    color: '#FF9A3D',
    of: (region: RegionIndicators) => region.bikeway_km_per_10k,
    format: (value: number | null) => (value === null ? '—' : `${dec(value, 1)} km`),
    note: 'Km de ciclovia, ciclofaixa e calçada compartilhada dentro da RA (IDE-DF), por 10 mil habitantes do Censo 2022. Mede extensão instalada, não uso nem qualidade.',
  },
  {
    key: 'health',
    label: 'Saúde / 10 mil hab.',
    color: '#00D4FF',
    of: (region: RegionIndicators) => region.health_facilities_per_10k,
    format: (value: number | null) => (value === null ? '—' : dec(value, 1)),
    note: 'Estabelecimentos cadastrados no CNES. É oferta instalada, não produção de atendimentos — e a maioria dos registros são clínicas e consultórios privados.',
  },
  {
    key: 'temperature',
    label: 'Temperatura média',
    color: '#A86BFF',
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
      color: '#FFFFFF',
      points: allYears.map((year) => ({ x: String(year), y: byYear.get(year) ?? null })),
    },
  ]
})

const securityChart = computed<Series[]>(() => {
  const crimes = securitySeries.value.filter((point) => point.metric_type === 'CRIME')
  const months = [...new Set(crimes.map((point) => point.reference_month_start))].sort()
  const categories = [
    { code: 'CVLI', label: 'CVLI', color: '#FF006A' },
    { code: 'CCP', label: 'Crimes contra o patrimônio', color: '#FF9A3D' },
    { code: 'OUTROS', label: 'Outros crimes', color: '#00D4FF' },
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
      color: '#FF9A3D',
      points: points.map((point) => ({
        x: point.reference_month_start,
        y: point.temp_max_avg_c,
        partial: point.days_observed < 28,
      })),
    },
    {
      key: 'tmin',
      label: 'Mínima média',
      color: '#A86BFF',
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
    color: '#00D4FF',
    points: weatherSeries.value.map((point) => ({
      x: point.reference_month_start,
      y: point.precipitation_mm,
      partial: point.days_observed < 28,
    })),
  },
])

const totals = computed(() => {
  const list = indicators.value
  const schoolYears = educationYears.value.filter((year) => year.scope === 'DF')
  const lastSchoolYear = schoolYears.reduce<EducationYear | null>(
    (latest, year) => (latest === null || year.census_year > latest.census_year ? year : latest),
    null,
  )
  return {
    crimes: list.reduce((sum, region) => sum + (region.crimes_total ?? 0), 0),
    facilities: list.reduce((sum, region) => sum + region.health_facilities, 0),
    withCrimeData: list.filter((region) => region.security_reference_year !== null).length,
    schools: lastSchoolYear?.schools_total ?? null,
    schoolsYear: lastSchoolYear?.census_year ?? null,
    bikewayKm: mobilityRegions.value.reduce((sum, region) => sum + region.bikeway_km, 0),
    metroStations: mobilityRegions.value.reduce((sum, region) => sum + region.metro_stations, 0),
  }
})

/** Um número por domínio, com a ressalva do que ele mede — e do que não mede. */
const domainSummary = computed(() => [
  {
    key: 'population',
    label: 'População',
    color: '#FFFFFF',
    value: num(overview.value?.population_df_latest),
    note: `Habitantes no DF em ${overview.value?.population_df_latest_year ?? '—'}. Por RA, só o Censo mede.`,
  },
  {
    key: 'security',
    label: 'Segurança',
    color: '#FF006A',
    value: short(totals.value.crimes),
    note: `Crimes registrados no último ano completo de cada uma das ${totals.value.withCrimeData} RAs com publicação.`,
  },
  {
    key: 'health',
    label: 'Saúde',
    color: '#00D4FF',
    value: num(totals.value.facilities),
    note: 'Estabelecimentos do CNES localizados em uma RA. Infraestrutura instalada, não atendimentos.',
  },
  {
    key: 'education',
    label: 'Educação',
    color: '#7CFFB2',
    value: num(totals.value.schools),
    note: `Escolas no Censo Escolar de ${totals.value.schoolsYear ?? '—'} (SEEDF). Matrícula é contada onde a escola fica, não onde o aluno mora.`,
  },
  {
    key: 'mobility',
    label: 'Mobilidade',
    color: '#FF9A3D',
    value: `${dec(totals.value.bikewayKm, 1)} km`,
    note: `Malha cicloviária mapeada pelo IDE-DF, mais ${totals.value.metroStations} estações de metrô em operação. Mede extensão, não uso.`,
  },
  {
    key: 'weather',
    label: 'Clima',
    color: '#A86BFF',
    value: weatherSeries.value.length
      ? temperature(weatherSeries.value[weatherSeries.value.length - 1].temp_mean_c)
      : '—',
    note: 'Temperatura média do último mês observado. Reanálise ERA5/Open-Meteo, não medição do INMET.',
  },
])

async function load() {
  loading.value = true
  error.value = null
  try {
    const [overviewData, geo, indicatorList, populationSeries, security, weather, education, mobility] =
      await Promise.all([
        api.overview(),
        api.regionsGeoJSON(),
        api.indicators(),
        api.population({ scope: 'df' }),
        api.securitySummary({ year_from: 2018 }),
        api.weatherSummary({ year_from: 2022 }),
        api.education(),
        api.mobility(),
      ])
    overview.value = overviewData
    features.value = geo.features
    indicators.value = indicatorList
    populationDF.value = populationSeries
    securitySeries.value = security
    weatherSeries.value = weather
    educationYears.value = education
    mobilityRegions.value = mobility
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
    <section>
      <p v-reveal class="label">
        35 Regiões Administrativas · 6 domínios · 10 fontes oficiais
      </p>
      <h1
        v-reveal
        class="mt-4 font-display text-[2.4rem] font-bold uppercase leading-[0.92] tracking-tight
               min-[400px]:text-[2.75rem] sm:text-[4.5rem]"
        style="font-stretch: 118%"
      >
        Brasília<br />
        <span class="text-accent">através dos dados</span>
      </h1>
      <div v-reveal.rule class="mt-6 h-px w-full bg-line" />
      <p v-reveal class="mt-5 max-w-2xl text-sm leading-relaxed text-muted">
        Dados públicos de população, segurança, saúde, educação, mobilidade e clima, consolidados
        por Região Administrativa. Onde a fonte não publica, a interface mostra um traço — nunca
        um zero.
      </p>
    </section>

    <LoadState :loading="loading" :error="error" @retry="load">
      <!-- KPIs -->
      <!-- Celular: 2 colunas, com os dois valores longos (população e data)
           ocupando a linha inteira — número cortado no meio é pior que rolar. -->
      <section class="grid grid-cols-2 gap-px border border-line bg-line lg:grid-cols-4">
        <KpiCard
          class="col-span-2 sm:col-span-1"
          label="População do DF"
          :count="overview?.population_df_latest ?? null"
          :format="num"
          :hint="
            overview
              ? `Habitantes. ${overview.population_df_is_projection ? 'Projeção' : 'Censo'} do IBGE para ${overview.population_df_latest_year}`
              : ''
          "
          accent="#FFFFFF"
        />
        <KpiCard
          label="Regiões Administrativas"
          :count="overview?.regions_total ?? null"
          :hint="`${overview?.regions_with_all_domains ?? 0} com dado publicado nos quatro domínios de série longa`"
        />
        <KpiCard
          label="Indicadores monitorados"
          :count="overview?.indicators_monitored ?? null"
          :hint="`${overview?.sources_total ?? 0} fontes catalogadas · ${overview?.government_sources_total ?? 0} do GDF`"
        />
        <KpiCard
          class="col-span-2 sm:col-span-1"
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
      <!-- `grid-cols-1` + `min-w-0`: sem coluna explícita, a faixa de botões
           (que rola na horizontal) impunha a própria largura ao grid e a página
           inteira ficava com ~600px num celular de 390px. -->
      <section class="mt-8 grid grid-cols-1 gap-6 sm:mt-10 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
        <div class="card card-pad min-w-0">
          <div class="mb-5 flex flex-wrap items-start justify-between gap-4">
            <div class="min-w-0">
              <h2 class="section-title">Mapa do Distrito Federal</h2>
              <p class="label mt-2">
                35 Regiões Administrativas · {{ fine ? 'clique para abrir o detalhe' : 'toque para ver o valor' }}
              </p>
            </div>
            <div class="rail w-full sm:w-auto" role="tablist" aria-label="Indicador do mapa">
              <button
                v-for="item in METRICS"
                :key="item.key"
                type="button"
                role="tab"
                :aria-selected="metricKey === item.key"
                class="min-h-[40px] border px-3 py-2 font-mono text-[11px] uppercase tracking-[0.1em]
                       transition-colors sm:min-h-0 sm:px-2.5 sm:py-1.5 sm:text-[10px]"
                :class="
                  metricKey === item.key
                    ? 'border-transparent text-night'
                    : 'border-line text-faint hover:text-ink'
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

          <RegionPicker
            class="mt-4 sm:hidden"
            :regions="features.map((f) => ({ id: f.properties.region_id, name: f.properties.region_name }))"
          />
        </div>

        <div class="card card-pad min-w-0">
          <h2 class="section-title">Ranking · {{ metric.label }}</h2>
          <p class="label mb-4 mt-2">Maiores valores entre as 35 RAs</p>
          <RankBars
            :items="ranking"
            :color="metric.color"
            :format-value="(value) => metric.format(value)"
            :selected-id="hoveredRegion"
            :limit="rankingLimit"
            @select="router.push(`/regiao/${$event}`)"
          />
          <button
            v-if="!showAllRanking"
            type="button"
            class="mt-4 h-11 w-full border border-line font-mono text-[11px] uppercase tracking-[0.12em]
                   text-muted transition-colors hover:border-accent hover:text-ink"
            @click="showAllRanking = true"
          >
            Ver as 35 regiões
          </button>
        </div>
      </section>

      <!-- Os seis domínios, cada um com o número que a fonte publica hoje -->
      <section class="mt-10 sm:mt-12">
        <h2 v-reveal class="section-title">Seis domínios</h2>
        <div v-reveal.rule class="mt-4 h-px w-full bg-line" />
        <div class="mt-px grid gap-px bg-line sm:grid-cols-2 lg:grid-cols-3">
          <div
            v-for="domain in domainSummary"
            :key="domain.key"
            v-reveal
            class="card-pad relative bg-surface"
          >
            <span
              class="absolute left-0 top-0 h-full w-[3px]"
              :style="{ background: domain.color }"
              aria-hidden="true"
            />
            <p class="label" :style="{ color: domain.color }">{{ domain.label }}</p>
            <p class="metric mt-3">{{ domain.value }}</p>
            <p class="mt-3 font-mono text-[11px] leading-relaxed text-faint">{{ domain.note }}</p>
          </div>
        </div>
      </section>

      <!-- Séries temporais -->
      <section class="mt-8 grid grid-cols-1 gap-6 sm:mt-10 lg:grid-cols-2">
        <div class="card card-pad min-w-0">
          <h2 class="section-title">Evolução da população do DF</h2>
          <p class="label mb-5 mt-2">
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

        <div class="card card-pad min-w-0">
          <h2 class="section-title">Crimes registrados por mês</h2>
          <p class="label mb-5 mt-2">
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

        <div class="card card-pad min-w-0">
          <h2 class="section-title">Temperatura média mensal</h2>
          <p class="label mb-5 mt-2">Média das 35 RAs · ERA5/Open-Meteo</p>
          <LineChart
            :series="weatherChart"
            :format-value="(value) => `${dec(value, 0)}°`"
            :format-x="monthLabel"
            :area="false"
            :y-zero="false"
          />
        </div>

        <div class="card card-pad min-w-0">
          <h2 class="section-title">Precipitação mensal</h2>
          <p class="label mb-5 mt-2">
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
