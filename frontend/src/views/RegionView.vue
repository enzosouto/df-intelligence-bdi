<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { api, apiUrl } from '@/api'
import { dec, monthLabel, num, pct, temperature } from '@/format'
import type {
  BikewayYear,
  Coverage,
  EducationYear,
  HealthSummary,
  MobilityRegion,
  RegionIndicators,
  SecurityPoint,
  WeatherPoint,
} from '@/types'
import type { Series } from '@/components/chart'
import LineChart from '@/components/LineChart.vue'
import LoadState from '@/components/LoadState.vue'
import DataNotice from '@/components/DataNotice.vue'
import RegionPicker from '@/components/RegionPicker.vue'

const props = defineProps<{ regionId: string }>()

const loading = ref(true)
const error = ref<string | null>(null)

const region = ref<RegionIndicators | null>(null)
const security = ref<SecurityPoint[]>([])
const weather = ref<WeatherPoint[]>([])
const health = ref<HealthSummary | null>(null)
const education = ref<EducationYear[]>([])
const mobility = ref<MobilityRegion | null>(null)
const bikeways = ref<BikewayYear[]>([])
const coverage = ref<Coverage | null>(null)
const allRegions = ref<{ id: string; name: string }[]>([])

/** Atalhos da página: no celular ela tem ~5 telas de altura. */
const sections = computed(() =>
  [
    { id: 'seguranca', label: 'Segurança', color: '#FF006A', show: true },
    { id: 'saude', label: 'Saúde', color: '#00D4FF', show: !!health.value },
    { id: 'educacao', label: 'Educação', color: '#7CFFB2', show: education.value.length > 0 },
    { id: 'mobilidade', label: 'Mobilidade', color: '#FF9A3D', show: !!mobility.value },
    { id: 'clima', label: 'Clima', color: '#A86BFF', show: true },
  ].filter((section) => section.show),
)

/**
 * Compartilhar: a folha nativa do sistema no celular (WhatsApp, e-mail…);
 * onde ela não existe, o link vai para a área de transferência.
 */
const shareState = ref<'idle' | 'copied'>('idle')
const canShare = typeof navigator !== 'undefined' && 'share' in navigator
async function share() {
  if (!region.value) return
  const data = {
    title: `${region.value.region_name} · DF Intelligence`,
    text: `Dados públicos de ${region.value.region_name} (DF): população, segurança, saúde, educação, mobilidade e clima.`,
    url: window.location.href,
  }
  try {
    if (canShare) {
      await navigator.share(data)
    } else {
      await navigator.clipboard.writeText(data.url)
      shareState.value = 'copied'
      window.setTimeout(() => (shareState.value = 'idle'), 2200)
    }
  } catch {
    // Cancelar a folha de compartilhamento não é erro.
  }
}
const parentName = ref<string | null>(null)

const securityChart = computed<Series[]>(() => {
  const crimes = security.value.filter((point) => point.metric_type === 'CRIME')
  const months = [...new Set(crimes.map((point) => point.reference_month_start))].sort()
  const categories = [
    { code: 'CVLI', label: 'CVLI', color: '#FF006A' },
    { code: 'CCP', label: 'Patrimônio', color: '#FF9A3D' },
    { code: 'OUTROS', label: 'Outros', color: '#00D4FF' },
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

// Etapas por ano. Ano incompleto chega com null e vira quebra na linha —
// em 8 dos 12 anos, o arquivo de matrículas da SEEDF omite escolas ativas do cadastro.
const educationChart = computed<Series[]>(() => {
  const stages = [
    { key: 'early_childhood', label: 'Educação infantil', color: '#7CFFB2' },
    { key: 'elementary', label: 'Fundamental', color: '#00D4FF' },
    { key: 'high_school_all', label: 'Médio (com integrado)', color: '#A86BFF' },
    { key: 'youth_adult', label: 'EJA', color: '#FF9A3D' },
  ] as const
  return stages.map((stage) => ({
    key: stage.key,
    label: stage.label,
    color: stage.color,
    points: education.value.map((year) => ({ x: String(year.census_year), y: year[stage.key] })),
  }))
})

// Só os tipos presentes na RA: "Ciclofaixa 0,0 km" na legenda é ruído.
const bikewayParts = computed(() => {
  const region = mobility.value
  if (!region) return []
  return [
    { key: 'seg', label: 'Ciclovia', value: region.bikeway_km_segregated, color: '#FF9A3D' },
    { key: 'paint', label: 'Ciclofaixa', value: region.bikeway_km_painted, color: '#FFB38A' },
    { key: 'shared', label: 'Calçada compartilhada', value: region.bikeway_km_shared, color: '#98A2B3' },
    { key: 'other', label: 'Outros', value: region.bikeway_km_other, color: '#5D6675' },
  ].filter((part) => part.value > 0)
})

const educationGaps = computed(() =>
  education.value.filter((year) => !year.is_year_complete).map((year) => year.census_year),
)

// Acumulado dos trechos que existem hoje, por ano de construção. O rótulo do
// gráfico diz isso — não é a malha histórica.
const bikewayChart = computed<Series[]>(() => [
  {
    key: 'bikeway',
    label: 'Km acumulados (malha atual)',
    color: '#FF9A3D',
    points: bikeways.value.map((year) => ({
      x: String(year.construction_year),
      y: year.current_network_km_cumulative,
    })),
  },
])

const weatherChart = computed<Series[]>(() => [
  {
    key: 'tmax',
    label: 'Máxima média',
    color: '#FF9A3D',
    points: weather.value.map((point) => ({
      x: point.reference_month_start,
      y: point.temp_max_avg_c,
      partial: point.days_observed < 28,
    })),
  },
  {
    key: 'tmin',
    label: 'Mínima média',
    color: '#A86BFF',
    points: weather.value.map((point) => ({
      x: point.reference_month_start,
      y: point.temp_min_avg_c,
      partial: point.days_observed < 28,
    })),
  },
])

const rainChart = computed<Series[]>(() => [
  {
    key: 'rain',
    label: 'Precipitação',
    color: '#00D4FF',
    points: weather.value.map((point) => ({
      x: point.reference_month_start,
      y: point.precipitation_mm,
      partial: point.days_observed < 28,
    })),
  },
])

async function load() {
  loading.value = true
  error.value = null
  parentName.value = null
  try {
    const [indicators, securityData, weatherData, healthData, coverageData, educationData, mobilityData, bikewayData] =
      await Promise.all([
      api.regionIndicators(props.regionId),
      api.securitySummary({ region_id: props.regionId, year_from: 2018 }),
      api.weather({ region_id: props.regionId, year_from: 2022, limit: 600 }),
      api.health({ region_id: props.regionId }),
      api.coverage(),
      api.education({ region_id: props.regionId }),
      api.mobility({ region_id: props.regionId }),
      api.bikewayYearly({ region_id: props.regionId }),
    ])
    region.value = indicators
    security.value = securityData
    weather.value = weatherData
    health.value = healthData[0] ?? null
    education.value = educationData
    mobility.value = mobilityData[0] ?? null
    bikeways.value = bikewayData
    coverage.value = coverageData.find((item) => item.region_id === props.regionId) ?? null
    allRegions.value = coverageData.map((item) => ({ id: item.region_id, name: item.region_name }))

    if (indicators.inferred_parent_region_id) {
      parentName.value = (await api.region(indicators.inferred_parent_region_id)).region_name
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.regionId, load)
</script>

<template>
  <div class="space-y-8">
    <RouterLink
      to="/"
      class="-my-2 inline-flex min-h-[44px] items-center gap-1.5 text-xs text-muted hover:text-ink"
    >
      <span aria-hidden="true">←</span> Voltar ao painel
    </RouterLink>

    <LoadState :loading="loading" :error="error" @retry="load">
      <template v-if="region">
        <!-- Identidade -->
        <header>
          <p class="label">Região Administrativa · {{ region.region_id }}</p>
          <h1 class="mt-2 font-display text-4xl font-bold tracking-tight sm:text-5xl">
            {{ region.region_name }}
          </h1>
          <p class="mt-3 text-sm text-muted">
            {{ dec(region.area_km2, 1) }} km²
            <span v-if="region.density_2022_per_km2">
              · {{ dec(region.density_2022_per_km2, 1) }} hab/km²
            </span>
          </p>

          <div class="mt-5 flex gap-2 sm:max-w-md">
            <RegionPicker
              class="min-w-0 flex-1"
              :regions="allRegions"
              :current="region.region_id"
              label="Trocar de região"
            />
            <button
              type="button"
              class="flex h-11 shrink-0 items-center gap-2 border border-line px-3 font-mono text-[11px]
                     uppercase tracking-[0.1em] text-muted transition-colors hover:border-accent hover:text-ink"
              :aria-label="canShare ? 'Compartilhar esta região' : 'Copiar link desta região'"
              @click="share"
            >
              <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
                <path d="M12 3v12M7 8l5-5 5 5M5 13v8h14v-8" />
              </svg>
              <span class="hidden min-[400px]:inline">{{ shareState === 'copied' ? 'Copiado' : canShare ? 'Compartilhar' : 'Copiar link' }}</span>
            </button>
          </div>
        </header>

        <!-- Atalhos das seções: fixos sob o cabeçalho no celular. -->
        <nav
          class="sticky top-[calc(3.5rem+env(safe-area-inset-top))] z-30 -mx-4 border-y border-line
                 bg-night/95 px-4 backdrop-blur-sm sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:px-0"
          aria-label="Seções desta região"
        >
          <div class="rail py-2 sm:py-0">
            <a
              v-for="section in sections"
              :key="section.id"
              :href="`#${section.id}`"
              class="inline-flex min-h-[36px] items-center gap-2 border border-line px-3 font-mono
                     text-[11px] uppercase tracking-[0.1em] text-muted transition-colors hover:text-ink"
              @click.prevent="$router.replace({ hash: `#${section.id}` })"
            >
              <span class="h-1.5 w-1.5" :style="{ background: section.color }" aria-hidden="true" />
              {{ section.label }}
            </a>
          </div>
        </nav>

        <!-- Indicadores principais -->
        <section class="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          <div class="card card-pad">
            <p class="label" style="color: #ffffff">População</p>
            <p class="metric mt-2">{{ num(region.population_2022) }}</p>
            <p class="mt-2 text-xs text-faint">Censo 2022 (IBGE)</p>
          </div>
          <div class="card card-pad">
            <p class="label" style="color: #ffffff">Densidade</p>
            <p class="metric mt-2">{{ dec(region.density_2022_per_km2, 0) }}</p>
            <p class="mt-2 text-xs text-faint">hab/km² · área de {{ dec(region.area_km2, 1) }} km²</p>
          </div>
          <div class="card card-pad">
            <p class="label" style="color: #ff006a">Segurança</p>
            <p class="metric mt-2">{{ num(region.crimes_total) }}</p>
            <p class="mt-2 text-xs text-faint">
              <template v-if="region.security_reference_year">
                crimes em {{ region.security_reference_year }} ·
                {{ dec(region.crimes_per_10k, 1) }} por 10 mil hab.
              </template>
              <template v-else>sem ano completo publicado</template>
            </p>
          </div>
          <div class="card card-pad">
            <p class="label" style="color: #00d4ff">Saúde</p>
            <p class="metric mt-2">{{ num(region.health_facilities) }}</p>
            <p class="mt-2 text-xs text-faint">
              estabelecimentos · {{ num(region.health_facilities_sus_ambulatory) }} com atendimento ambulatorial SUS
            </p>
          </div>
          <div class="card card-pad">
            <p class="label" style="color: #7cffb2">Educação</p>
            <p class="metric mt-2">{{ num(region.education_schools) }}</p>
            <p class="mt-2 text-xs text-faint">
              escolas · {{ num(region.education_enrollment) }} matrículas
              <template v-if="region.education_reference_year">em {{ region.education_reference_year }}</template>
            </p>
          </div>
          <div class="card card-pad">
            <p class="label" style="color: #ff9a3d">Mobilidade</p>
            <p class="metric mt-2">{{ dec(region.bikeway_km, 1) }}<span class="text-base text-muted"> km</span></p>
            <p class="mt-2 text-xs text-faint">
              de malha cicloviária · {{ num(region.metro_stations) }} estações de metrô
            </p>
          </div>
          <div class="card card-pad">
            <p class="label" style="color: #a86bff">Clima</p>
            <p class="metric mt-2">{{ temperature(region.temp_mean_c) }}</p>
            <p class="mt-2 text-xs text-faint">
              média {{ region.weather_first_year }}–{{ region.weather_last_year }} ·
              {{ dec(region.rainy_days_per_year, 0) }} dias de chuva/ano
            </p>
          </div>
        </section>

        <!-- População: o ponto onde é mais fácil concluir errado -->
        <section class="card card-pad">
          <h2 class="section-title">População nos Censos</h2>
          <div class="mt-5 flex flex-wrap items-end gap-x-10 gap-y-5">
            <div>
              <p class="label">Censo 2010</p>
              <p class="mt-1 font-display text-2xl font-semibold tnum">
                {{ region.existed_in_2010 ? num(region.population_2010) : '—' }}
              </p>
            </div>
            <div>
              <p class="label">Censo 2022</p>
              <p class="mt-1 font-display text-2xl font-semibold tnum">
                {{ num(region.population_2022) }}
              </p>
            </div>
            <div v-if="region.is_growth_comparable">
              <p class="label">Variação</p>
              <p
                class="mt-1 font-display text-2xl font-semibold tnum"
                :style="{
                  color: (region.population_change_pct_2010_2022 ?? 0) >= 0 ? '#FFFFFF' : '#FF006A',
                }"
              >
                {{ pct(region.population_change_pct_2010_2022) }}
              </p>
              <p class="mt-1 text-xs text-faint">
                {{ pct(region.population_cagr_pct_2010_2022, 2) }} ao ano
              </p>
            </div>
          </div>

          <DataNotice v-if="!region.existed_in_2010" tone="warn" class="mt-5">
            Esta RA não existia como subdistrito no Censo 2010 — sua população naquele ano estava
            contabilizada
            <template v-if="parentName">em {{ parentName }}</template>
            <template v-else>na RA de origem</template>. Por isso não há comparação entre os dois
            Censos.
          </DataNotice>

          <DataNotice
            v-else-if="!region.is_growth_comparable"
            tone="warn"
            class="mt-5"
          >
            Entre 2010 e 2022, parte do território desta RA foi transferida para Regiões
            Administrativas criadas no período. Comparar os dois Censos mostraria uma "queda"
            populacional que é redefinição de limite, não perda de habitantes — por isso a variação
            não é publicada aqui.
          </DataNotice>
        </section>

        <!-- Segurança -->
        <section id="seguranca" class="card card-pad min-w-0 scroll-mt-28">
          <div class="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 class="section-title">Ocorrências por mês</h2>
              <p class="mt-1 text-xs text-faint">Balanço Criminal da SSP-DF, a partir de 2018</p>
            </div>
            <div v-if="region.police_activity_total" class="text-right">
              <p class="label">Produtividade policial</p>
              <p class="mt-1 font-display text-xl font-semibold tnum">
                {{ num(region.police_activity_total) }}
              </p>
            </div>
          </div>

          <LineChart
            class="mt-6"
            :series="securityChart"
            :format-value="(value) => num(value)"
            :format-x="monthLabel"
            :area="false"
          />

          <DataNotice class="mt-4">
            Tráfico de drogas, porte de arma e recuperação de veículos são contados à parte, como
            produtividade policial: eles sobem quando a polícia atua mais, não quando a região fica
            mais violenta.
          </DataNotice>

          <DataNotice
            v-if="coverage && coverage.security_missing_years.length"
            tone="warn"
            class="mt-3"
          >
            A SSP-DF não publica o balanço desta RA em
            {{ coverage.security_missing_years.join(', ') }}. Os meses correspondentes aparecem como
            lacuna na linha, nunca como zero.
          </DataNotice>
        </section>

        <!-- Saúde -->
        <section v-if="health" id="saude" class="card card-pad min-w-0 scroll-mt-28">
          <h2 class="section-title">Rede de saúde instalada</h2>
          <p class="mt-1 text-xs text-faint">Cadastro Nacional de Estabelecimentos de Saúde</p>

          <dl class="mt-6 grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
            <div v-for="item in [
              { label: 'Total', value: health.facilities_total, title: 'Estabelecimentos cadastrados no CNES nesta RA' },
              { label: 'Públicos', value: health.facilities_public, title: 'Natureza jurídica de administração pública' },
              { label: 'Privados', value: health.facilities_private, title: 'Entidades empresariais e pessoas físicas' },
              { label: 'Ambulatorial SUS', value: health.facilities_sus_ambulatory, title: 'Fazem atendimento ambulatorial pelo SUS' },
              { label: 'Hospitalares', value: health.facilities_hospital, title: 'Hospitais, prontos-socorros e unidades mistas' },
              { label: 'Ambulatoriais', value: health.facilities_ambulatory, title: 'Consultórios, clínicas, centros e postos de saúde' },
              { label: 'Diagnóstico e terapia', value: health.facilities_diagnostics, title: 'SADT, laboratórios, imunização e hemoterapia' },
              { label: 'Por 10 mil hab.', value: health.facilities_per_10k, title: 'Estabelecimentos por 10 mil habitantes (Censo 2022)' },
            ]" :key="item.label">
              <dt class="label" :title="item.title">{{ item.label }}</dt>
              <dd class="mt-1 font-display text-xl font-semibold tnum">
                {{ typeof item.value === 'number' && !Number.isInteger(item.value) ? dec(item.value, 1) : num(item.value) }}
              </dd>
            </div>
          </dl>

          <DataNotice class="mt-5">
            Mede infraestrutura cadastrada, não atendimentos realizados — o CNES não informa
            produção. Dos estabelecimentos desta RA,
            {{ num(health.assigned_by_neighborhood) }} foram localizados pelo bairro informado por
            falta de coordenada no cadastro.
          </DataNotice>
        </section>

        <!-- Educação -->
        <section v-if="education.length" id="educacao" class="card card-pad min-w-0 scroll-mt-28">
          <h2 class="section-title">Matrículas por etapa</h2>
          <p class="mb-5 mt-1 text-xs text-faint">
            Censo Escolar · todas as redes · escolas localizadas nesta RA
          </p>
          <LineChart :series="educationChart" :area="false" :format-value="(value) => num(value)" />

          <dl class="mt-6 grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
            <div v-for="item in [
              { label: 'Escolas', value: region.education_schools, title: 'Unidades escolares de todas as redes na RA' },
              { label: 'Escolas públicas', value: region.education_schools_public, title: 'Rede distrital e federal' },
              { label: 'Matrículas', value: region.education_enrollment, title: 'Total publicado pela SEEDF no ano de referência' },
              { label: 'Na rede pública', value: region.education_enrollment_public_share_pct, title: 'Participação da rede pública nas matrículas', suffix: '%' },
            ]" :key="item.label">
              <dt class="label" :title="item.title">{{ item.label }}</dt>
              <dd class="mt-1 font-display text-xl font-semibold tnum">
                {{ item.suffix ? `${dec(item.value, 1)}${item.value === null ? '' : item.suffix}` : num(item.value) }}
              </dd>
            </div>
          </dl>

          <DataNotice class="mt-5">
            Matrícula é contada onde a escola fica, não onde o aluno mora — por isso não há taxa
            por habitante. A região de cada escola vem da coordenada, não do código declarado pela
            SEEDF, que está invertido entre Arapoanga e Água Quente.
          </DataNotice>
          <DataNotice v-if="educationGaps.length" tone="warn" class="mt-3">
            {{ educationGaps.join(', ') }}: o arquivo de matrículas publicado não cobre as escolas
            do cadastro. O ano aparece como lacuna na linha, não como queda.
          </DataNotice>
        </section>

        <!-- Mobilidade -->
        <section v-if="mobility" id="mobilidade" class="card card-pad min-w-0 scroll-mt-28">
          <h2 class="section-title">Mobilidade</h2>
          <p class="mt-1 text-xs text-faint">
            Malha cicloviária e metrô · IDE-DF · trechos recortados pela divisa da RA
          </p>

          <dl class="mt-6 grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
            <div v-for="item in [
              { label: 'Malha cicloviária', value: `${dec(mobility.bikeway_km, 1)} km`, title: 'Ciclovia, ciclofaixa, calçada compartilhada e outros' },
              { label: 'Por 10 mil hab.', value: mobility.bikeway_km_per_10k === null ? '—' : `${dec(mobility.bikeway_km_per_10k, 1)} km`, title: 'Censo 2022' },
              { label: 'Estações de metrô', value: num(mobility.metro_stations), title: 'Em operação' },
              { label: 'Metrô em obras', value: num(mobility.metro_stations_building), title: 'Estações registradas como em construção' },
            ]" :key="item.label">
              <dt class="label" :title="item.title">{{ item.label }}</dt>
              <dd class="mt-1 font-display text-xl font-semibold tnum">{{ item.value }}</dd>
            </div>
          </dl>

          <div v-if="mobility.bikeway_km > 0" class="mt-6">
            <p class="label mb-2">Tipo de infraestrutura</p>
            <div class="flex h-2.5 bg-elevated">
              <div
                v-for="part in bikewayParts"
                :key="part.key"
                :style="{ width: `${(100 * part.value) / mobility.bikeway_km}%`, background: part.color }"
              />
            </div>
            <p class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
              <span v-for="part in bikewayParts" :key="part.key" class="inline-flex items-center gap-1.5">
                <span class="inline-block h-2 w-2" :style="{ background: part.color }" />
                {{ part.label }} {{ dec(part.value, 1) }} km
              </span>
            </p>
          </div>

          <div v-if="mobility.bikeway_km > 0" class="mt-6">
            <p class="label mb-3">Malha atual por ano de construção (acumulado)</p>
            <LineChart :series="bikewayChart" :format-value="(value) => `${dec(value, 0)} km`" />
          </div>

          <DataNotice class="mt-5">
            A série mostra os trechos que existem hoje, pelo ano em que foram construídos — não a
            malha de cada ano, porque trechos removidos não aparecem na fonte. Estação na RA é
            presença, não acesso a pé para todos os moradores.
          </DataNotice>
        </section>

        <!-- Clima -->
        <section id="clima" class="grid scroll-mt-28 grid-cols-1 gap-6 lg:grid-cols-2">
          <div class="card card-pad min-w-0">
            <h2 class="section-title">Temperatura</h2>
            <p class="mb-5 mt-1 text-xs text-faint">
              Máxima e mínima médias por mês · ERA5/Open-Meteo
            </p>
            <LineChart
              :series="weatherChart"
              :format-value="(value) => `${dec(value, 0)}°`"
              :format-x="monthLabel"
              :area="false"
              :y-zero="false"
            />
          </div>
          <div class="card card-pad min-w-0">
            <h2 class="section-title">Chuva</h2>
            <p class="mb-5 mt-1 text-xs text-faint">Acumulado mensal</p>
            <LineChart
              :series="rainChart"
              :format-value="(value) => `${dec(value, 0)} mm`"
              :format-x="monthLabel"
            />
          </div>
        </section>

        <DataNotice tone="warn">
          O clima vem do Open-Meteo/ERA5, fonte externa e não governamental — reanálise
          interpolada, não medição de estação do INMET.
          <template v-if="(region.weather_regions_sharing_cell ?? 1) > 1">
            A resolução do modelo é maior que esta RA: a série é idêntica à de outras
            {{ (region.weather_regions_sharing_cell ?? 1) - 1 }} regiões que caem na mesma célula de
            amostragem.
          </template>
        </DataNotice>

        <p v-if="region" class="text-xs text-faint">
          <a
            v-if="region.region_id"
            class="link-underline inline-block py-3"
            :href="apiUrl(`/api/regions/${region.region_id}/indicators`)"
            target="_blank"
            rel="noopener"
          >
            Ver os dados desta região na API
          </a>
        </p>
      </template>
    </LoadState>
  </div>
</template>
