/**
 * Cliente da API.
 *
 * Em desenvolvimento, `VITE_API_BASE_URL` fica vazio e o Vite faz proxy de
 * `/api` para o backend. Em produção (container), a variável é injetada no
 * build e aponta para a API vista pelo navegador.
 */

import { ref } from 'vue'
import type {
  Coverage,
  EducationYear,
  BikewayYear,
  MobilityRegion,
  HealthSummary,
  Indicator,
  Insight,
  Overview,
  PipelineStatus,
  PopulationPoint,
  Region,
  RegionFeatureCollection,
  RegionIndicators,
  SecurityPoint,
  Source,
  WeatherPoint,
} from './types'

const BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

/**
 * Endereço absoluto de um caminho da API, para LINKS (documentação, JSON de
 * uma região). Em produção a API mora em outro domínio (Render); um href
 * relativo `/api/...` cairia no próprio site e voltaria a página inicial.
 */
export function apiUrl(path: string): string {
  return `${BASE}${path}`
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly path: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/**
 * A API gratuita do Render dorme após 15 min sem acesso e leva ~30–60 s para
 * acordar. Nesse intervalo o proxy do Render responde 502/503 (sem cabeçalho
 * CORS, então o navegador vê "falha de rede"). Em vez de mostrar erro na
 * primeira visita do dia, a chamada tenta de novo com espera crescente por até
 * ~75 s, e `apiWaking` avisa a interface para explicar a demora.
 */
export const apiWaking = ref(false)

const RETRY_DELAYS_MS = [1500, 3000, 5000, 8000, 12000, 15000, 15000, 15000]
const RETRYABLE = new Set([502, 503, 504])
const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

async function get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin)
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value))
    }
  }

  for (let attempt = 0; ; attempt += 1) {
    let response: Response | null = null
    try {
      response = await fetch(url.toString(), { headers: { Accept: 'application/json' } })
    } catch {
      response = null
    }

    if (response?.ok) {
      apiWaking.value = false
      return (await response.json()) as T
    }

    const retryable = response === null || RETRYABLE.has(response.status)
    if (!retryable || attempt >= RETRY_DELAYS_MS.length) {
      apiWaking.value = false
      throw response === null
        ? new ApiError('Não foi possível falar com a API.', 0, path)
        : new ApiError(`A API respondeu ${response.status}.`, response.status, path)
    }
    apiWaking.value = true
    await sleep(RETRY_DELAYS_MS[attempt])
  }
}

export const api = {
  overview: () => get<Overview>('/api/overview'),
  regions: () => get<Region[]>('/api/regions'),
  regionsGeoJSON: () => get<RegionFeatureCollection>('/api/regions/geojson'),
  region: (id: string) => get<Region>(`/api/regions/${id}`),
  regionIndicators: (id: string) => get<RegionIndicators>(`/api/regions/${id}/indicators`),
  indicators: (params?: { order_by?: string; descending?: boolean }) =>
    get<RegionIndicators[]>('/api/indicators', params),
  indicatorCatalog: () => get<Indicator[]>('/api/indicators/catalog'),
  population: (params?: { region_id?: string; scope?: 'region' | 'df' }) =>
    get<PopulationPoint[]>('/api/population', params),
  security: (params?: {
    region_id?: string
    category_code?: string
    metric_type?: 'CRIME' | 'POLICE_ACTIVITY'
    year_from?: number
    year_to?: number
    limit?: number
  }) => get<SecurityPoint[]>('/api/security', params),
  securitySummary: (params?: { region_id?: string; year_from?: number }) =>
    get<SecurityPoint[]>('/api/security/summary', params),
  health: (params?: { region_id?: string }) => get<HealthSummary[]>('/api/health', params),
  education: (params?: { region_id?: string }) => get<EducationYear[]>('/api/education', params),
  mobility: (params?: { region_id?: string }) => get<MobilityRegion[]>('/api/mobility', params),
  bikewayYearly: (params?: { region_id?: string }) =>
    get<BikewayYear[]>('/api/mobility/bikeways/yearly', params),
  weatherSummary: (params?: { year_from?: number }) =>
    get<WeatherPoint[]>('/api/weather/summary', params),
  weather: (params?: { region_id?: string; year_from?: number; year_to?: number; limit?: number }) =>
    get<WeatherPoint[]>('/api/weather', params),
  insights: (params?: { domain?: string }) => get<Insight[]>('/api/insights', params),
  sources: () => get<Source[]>('/api/sources'),
  coverage: () => get<Coverage[]>('/api/coverage'),
  pipeline: () => get<PipelineStatus[]>('/api/pipeline'),
}
