/** Contratos da API. Espelham `api/schemas.py`. */

export interface Region {
  region_id: string
  region_number: number
  region_name: string
  area_km2: number
  centroid_lat: number
  centroid_lon: number
  population_2022: number | null
  density_2022_per_km2: number | null
  monograph_url: string | null
}

export interface RegionIndicators {
  region_id: string
  region_name: string
  area_km2: number
  centroid_lat: number
  centroid_lon: number

  population_2022: number | null
  population_2010: number | null
  density_2022_per_km2: number | null
  existed_in_2010: boolean | null
  is_growth_comparable: boolean | null
  inferred_parent_region_id: string | null
  population_change_pct_2010_2022: number | null
  population_cagr_pct_2010_2022: number | null

  security_reference_year: number | null
  crimes_total: number | null
  cvli_total: number | null
  property_crimes_total: number | null
  violent_total: number | null
  police_activity_total: number | null
  crimes_per_10k: number | null
  cvli_per_100k: number | null

  health_facilities: number
  health_facilities_public: number
  health_facilities_sus_ambulatory: number
  health_facilities_hospital: number
  health_facilities_per_10k: number | null

  education_reference_year: number | null
  education_schools: number
  education_schools_public: number
  education_enrollment: number | null
  education_enrollment_public_share_pct: number | null

  bikeway_km: number | null
  bikeway_km_per_10k: number | null
  metro_stations: number | null

  temp_mean_c: number | null
  temp_max_avg_c: number | null
  temp_min_avg_c: number | null
  precipitation_mm_per_year: number | null
  rainy_days_per_year: number | null
  weather_first_year: number | null
  weather_last_year: number | null
  weather_regions_sharing_cell: number | null
}

export interface Overview {
  population_df_latest: number
  population_df_latest_year: number
  population_df_is_projection: boolean
  regions_total: number
  regions_with_all_domains: number
  indicators_monitored: number
  security_last_month: string | null
  weather_last_day: string | null
  data_last_updated_at: string | null
  sources_total: number
  government_sources_total: number
}

export interface PopulationPoint {
  region_id: string | null
  region_name: string | null
  reference_year: number
  population: number
  density_per_km2: number | null
  change_pct_since_previous: number | null
  years_since_previous: number | null
  source_id: string
}

export interface SecurityPoint {
  region_id: string
  region_name: string | null
  reference_month_start: string
  reference_year: number
  reference_month: number
  category_code: string
  category_name: string
  metric_type: 'CRIME' | 'POLICE_ACTIVITY'
  occurrences: number
  violent_occurrences: number | null
  occurrences_per_10k: number | null
}

export interface WeatherPoint {
  region_id: string
  reference_year: number
  reference_month: number
  reference_month_start: string
  days_observed: number
  temp_mean_c: number | null
  temp_max_avg_c: number | null
  temp_min_avg_c: number | null
  temp_max_absolute_c: number | null
  temp_min_absolute_c: number | null
  precipitation_mm: number | null
  rainy_days: number
  humidity_mean_pct: number | null
  regions_sharing_cell: number | null
}

export interface HealthSummary {
  region_id: string | null
  region_name: string | null
  facilities_total: number
  facilities_public: number
  facilities_private: number
  facilities_nonprofit: number
  facilities_sus_ambulatory: number
  facilities_hospital: number
  facilities_ambulatory: number
  facilities_urgent_care: number
  facilities_diagnostics: number
  facilities_support: number
  facilities_with_surgery_center: number
  facilities_with_obstetric_center: number
  assigned_by_coordinates: number
  assigned_by_neighborhood: number
  facilities_per_10k: number | null
}

export interface Insight {
  insight_id: string
  domain: 'population' | 'security' | 'health' | 'education' | 'mobility' | 'weather' | 'quality'
  title: string
  finding: string
  value_numeric: number | null
  unit: string | null
  period_start: number | null
  period_end: number | null
  method: string
  source_id: string
  caveat: string | null
}

export interface Source {
  source_id: string
  source_name: string
  organization: string
  domain: string
  url: string
  access_type: string
  granularity: string
  update_frequency: string
  is_df_government: boolean
  temporal_coverage: string
  caveat: string | null
}

export interface Coverage {
  region_id: string
  region_name: string
  population_2022_available: boolean
  population_2010_available: boolean
  security_years_with_data: number
  security_years_expected: number
  security_first_year: number | null
  security_last_year: number | null
  security_months_with_data: number
  security_missing_years: number[]
  health_facilities: number
  education_schools: number
  education_years_with_enrollment: number
  weather_first_day: string | null
  weather_last_day: string | null
  weather_days: number
  has_all_domains: boolean
}

/** Série anual do Censo Escolar. `null` é lacuna publicada, nunca zero. */
export interface EducationYear {
  scope: 'RA' | 'DF'
  region_id: string | null
  region_name: string | null
  census_year: number
  is_year_complete: boolean
  schools_total: number
  schools_public: number
  enrollment_total: number | null
  enrollment_public: number | null
  enrollment_public_share_pct: number | null
  early_childhood: number | null
  daycare: number | null
  preschool: number | null
  elementary: number | null
  high_school_all: number | null
  professional: number | null
  youth_adult: number | null
  special_total: number | null
  source_id: string
}

export interface MobilityRegion {
  region_id: string
  region_name: string | null
  bikeway_km: number
  bikeway_km_segregated: number
  bikeway_km_painted: number
  bikeway_km_shared: number
  bikeway_km_other: number
  bikeway_km_per_10k: number | null
  bikeway_first_year: number | null
  bikeway_last_year: number | null
  metro_stations: number
  metro_stations_building: number
  source_id: string
}

/** Km dos trechos que existem HOJE, por ano de construção — não a malha histórica. */
export interface BikewayYear {
  scope: 'RA' | 'DF'
  region_id: string | null
  construction_year: number
  current_network_km_built: number
  current_network_km_cumulative: number
  source_id: string
}

export interface PipelineStatus {
  source_key: string
  status: 'RUNNING' | 'SUCCESS' | 'FAILED'
  started_at: string
  finished_at: string | null
  duration_seconds: number | null
  rows_written: number
  requests_made: number
  error_message: string | null
  failed_error_checks: number
  failed_warning_checks: number
}

export interface Indicator {
  indicator_id: string
  domain: string
  name: string
  unit: string
  granularity: string
  source_id: string
  description: string
  caveat: string | null
}

export type GeoGeometry =
  | { type: 'Polygon'; coordinates: number[][][] }
  | { type: 'MultiPolygon'; coordinates: number[][][][] }

export interface RegionFeature {
  type: 'Feature'
  id: string
  geometry: GeoGeometry
  properties: {
    region_id: string
    region_name: string
    region_number: number
    area_km2: number
    population_2022: number | null
    density_2022_per_km2: number | null
    crimes_per_10k: number | null
    security_reference_year: number | null
    health_facilities: number | null
    temp_mean_c: number | null
  }
}

export interface RegionFeatureCollection {
  type: 'FeatureCollection'
  features: RegionFeature[]
}
