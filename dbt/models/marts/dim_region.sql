/*
  Dimensão das Regiões Administrativas — a espinha dorsal do modelo.

  Uma linha por RA, com identidade (código romano, número, nomes nas duas
  nomenclaturas), geografia (área geodésica, centroide, bounding box,
  geometria), população do Censo 2022 e as marcas de linhagem territorial que
  dizem quando a comparação 2010↔2022 é legítima.
*/

with regions as (
    select * from {{ ref('stg_regions') }}
),

lineage as (
    select * from {{ ref('int_region_lineage') }}
),

population as (
    select
        region_id,
        max(population) filter (where reference_year = 2022) as population_2022,
        max(population) filter (where reference_year = 2010) as population_2010
    from {{ ref('stg_population_census') }}
    group by region_id
)

select
    regions.region_id,
    regions.region_number,
    regions.region_name,
    regions.region_name_gdf,
    regions.ibge_subdistrict_id,
    regions.ibge_subdistrict_name,
    regions.name_match_method,
    regions.name_mapping_note,

    regions.area_km2,
    regions.centroid_lat,
    regions.centroid_lon,
    regions.bbox_min_lon,
    regions.bbox_min_lat,
    regions.bbox_max_lon,
    regions.bbox_max_lat,
    regions.geometry,
    regions.monograph_url,

    population.population_2022,
    population.population_2010,
    round(
        population.population_2022::numeric / nullif(regions.area_km2::numeric, 0), 1
    ) as density_2022_per_km2,

    lineage.existed_in_2010,
    lineage.inferred_parent_region_id,
    lineage.inferred_parent_border_share,
    lineage.lost_territory_after_2010,
    lineage.is_growth_comparable,

    -- Crescimento só é publicado onde a comparação é legítima.
    case
        when lineage.is_growth_comparable
             and population.population_2010 > 0
             and population.population_2022 is not null
        then round(
            100.0 * (population.population_2022 - population.population_2010)
                  / population.population_2010, 2)
    end as population_change_pct_2010_2022,

    -- Taxa geométrica anual equivalente no intervalo intercensitário (12 anos).
    case
        when lineage.is_growth_comparable
             and population.population_2010 > 0
             and population.population_2022 is not null
        then round(
            100.0 * (
                power(
                    population.population_2022::numeric / population.population_2010, 1.0 / 12
                ) - 1
            ), 2)
    end as population_cagr_pct_2010_2022

from regions
left join lineage    on lineage.region_id = regions.region_id
left join population on population.region_id = regions.region_id
