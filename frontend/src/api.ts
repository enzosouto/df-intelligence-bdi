/**
 * Cliente da API.
 *
 * Em desenvolvimento, `VITE_API_BASE_URL` fica vazio e o Vite faz proxy de
 * `/api` para o backend. Em produção (container), a variável é injetada no
 * build e aponta para a API vista pelo navegador.
 */

import type {
  Coverage,
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

async function get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin)
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value))
    }
  }

  let response: Response
  try {
    response = await fetch(url.toString(), { headers: { Accept: 'application/json' } })
  } catch {
    throw new ApiError('Não foi possível falar com a API.', 0, path)
  }

  if (!response.ok) {
    throw new ApiError(`A API respondeu ${response.status}.`, response.status, path)
  }
  return (await response.json()) as T
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
  weatherSummary: (params?: { year_from?: number }) =>
    get<WeatherPoint[]>('/api/weather/summary', params),
  weather: (params?: { region_id?: string; year_from?: number; year_to?: number; limit?: number }) =>
    get<WeatherPoint[]>('/api/weather', params),
  insights: (params?: { domain?: string }) => get<Insight[]>('/api/insights', params),
  sources: () => get<Source[]>('/api/sources'),
  coverage: () => get<Coverage[]>('/api/coverage'),
  pipeline: () => get<PipelineStatus[]>('/api/pipeline'),
}
