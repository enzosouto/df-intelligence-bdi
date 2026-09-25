# Dicionário de dados

Schemas: `raw` (ingestão), `staging` / `intermediate` (dbt, views),
`marts` (dbt, tabelas — o que a API lê), `meta` (observabilidade).

Convenções:

* `region_id` é sempre o código romano da RA (`RA-I` … `RA-XXXV`).
* Toda tabela `raw` tem `_source_url` e `_ingested_at`.
* **`NULL` significa "não publicado", nunca zero.**

---

## marts.dim_region

Uma linha por Região Administrativa. Grão: `region_id`.

| Coluna | Tipo | Descrição |
|---|---|---|
| `region_id` | text | **PK.** Código romano da RA. |
| `region_number` | int | Número da RA (1–35). |
| `region_name` | text | Nome oficial, grafia do IBGE. |
| `region_name_gdf` | text | Nome na grafia do GDF (caixa alta). |
| `ibge_subdistrict_id` | bigint | Subdistrito IBGE correspondente. Chave para o SIDRA. |
| `ibge_subdistrict_name` | text | Nome do subdistrito no IBGE. |
| `name_match_method` | text | `normalized_exact` ou `manual_reviewed`. |
| `name_mapping_note` | text | Justificativa, quando o casamento foi manual. |
| `area_km2` | float | Área geodésica calculada do polígono WGS84. |
| `centroid_lat` / `centroid_lon` | float | Ponto garantidamente **dentro** do polígono. |
| `bbox_*` | float | Retângulo envolvente. |
| `geometry` | jsonb | GeoJSON (WGS84). |
| `monograph_url` | text | Monografia oficial da RA, publicada pelo GDF. |
| `population_2022` | bigint | Censo 2022. `NULL` para Arapoanga e Água Quente. |
| `population_2010` | bigint | Censo 2010. `NULL` para as 16 RAs criadas depois. |
| `density_2022_per_km2` | numeric | `population_2022 / area_km2`. |
| `existed_in_2010` | bool | Existia como subdistrito no Censo 2010. |
| `inferred_parent_region_id` | text | RA de origem inferida. **Descritivo**, só preenchido quando ≥50% do contorno é compartilhado. |
| `inferred_parent_border_share` | numeric | Fração do contorno compartilhada com a origem inferida. |
| `lost_territory_after_2010` | bool | Faz fronteira com alguma RA criada após 2010. |
| `is_growth_comparable` | bool | **Sempre falso hoje.** Ver nota abaixo. |
| `population_change_pct_2010_2022` | numeric | Variação intercensitária. **Sempre `NULL`.** |
| `population_cagr_pct_2010_2022` | numeric | Variação anualizada. **Sempre `NULL`.** |

> **Nota sobre crescimento populacional.** As 19 RAs que existiam em 2010 todas
> cederam território às 16 criadas depois. Nenhuma comparação direta entre os
> Censos é válida por RA, e o projeto devolve `NULL` em vez de um número falso.
> Ver [`data_quality.md` §2.10](./data_quality.md).

---

## marts.dim_date

Grão: `date_key` (um dia). Cobre 2014-01-01 até o fim do ano corrente.

| Coluna | Tipo | Descrição |
|---|---|---|
| `date_key` | date | **PK.** |
| `year_number`, `month_number`, `day_of_month`, `quarter_number` | int | Partes da data. |
| `month_start` | date | Primeiro dia do mês. |
| `year_month` | text | `YYYY-MM`. |
| `month_name` | text | Nome do mês em português. |
| `season` | text | `SECA` (maio–setembro) ou `CHUVOSA`. |
| `is_past` | bool | Data já ocorreu. |

---

## marts.dim_category

Grão: `domain` + `category_id`. Unifica naturezas criminais e grupos de serviço
de saúde para que a API tenha uma forma só de listar filtros.

| Coluna | Tipo | Descrição |
|---|---|---|
| `domain` | text | `SECURITY` ou `HEALTH`. |
| `category_id` | text | `nature_key` (segurança) ou `service_group` (saúde). |
| `category_name` | text | Rótulo de exibição. |
| `parent_code` / `parent_name` | text | Categoria pai (`CVLI`, `CCP`, `OUTROS`, `PRODUTIVIDADE`, `CNES`). |
| `metric_type` | text | `CRIME`, `POLICE_ACTIVITY` ou `INFRASTRUCTURE`. |
| `is_violent` | bool | Crime com violência ou grave ameaça. `NULL` fora de segurança. |

---

## marts.dim_source

Grão: `source_id`. Catálogo de fontes — origem do campo `caveat` exibido na
interface.

| Coluna | Tipo | Descrição |
|---|---|---|
| `source_id` | text | **PK.** |
| `source_name`, `organization`, `domain`, `url` | text | Identificação da fonte. |
| `access_type` | text | API REST, página HTML + XLSX, etc. |
| `granularity` | text | Menor recorte disponível. |
| `update_frequency` | text | Periodicidade de publicação. |
| `is_df_government` | bool | Distingue fonte do GDF de federal/externa. |
| `temporal_coverage` | text | Período coberto. |
| `caveat` | text | Limitação metodológica conhecida. |

---

## marts.fct_population

Grão: `region_id` × `reference_year`. Só existem 2010 e 2022.

| Coluna | Tipo | Descrição |
|---|---|---|
| `region_id` | text | FK → `dim_region`. |
| `reference_year` | int | `2010` ou `2022`. |
| `population` | bigint | População residente. |
| `density_per_km2` | numeric | Sobre a área geodésica atual. |
| `existed_in_2010`, `is_growth_comparable` | bool | Marcas de linhagem. |
| `source_id` | text | FK → `dim_source`. |

---

## marts.fct_population_df

Grão: `reference_year`. Série anual do DF inteiro (2001–2026).

| Coluna | Tipo | Descrição |
|---|---|---|
| `reference_year` | int | **PK.** |
| `population` | bigint | Estimativa do IBGE. |
| `previous_year` | int | Ano anterior **disponível** (a série tem lacunas). |
| `years_since_previous` | int | Intervalo real até esse ano. |
| `change_pct_since_previous` | numeric | Variação no intervalo. |

> Anos de Censo e de revisão metodológica não têm estimativa publicada. As
> lacunas são preservadas como ausência de linha.

---

## marts.fct_security_monthly

Grão: `region_id` × `reference_year` × `reference_month` × `nature_key`.

| Coluna | Tipo | Descrição |
|---|---|---|
| `region_id` | text | FK → `dim_region`. |
| `reference_year`, `reference_month` | int | Período. |
| `reference_month_start` | date | Primeiro dia do mês. |
| `nature_key` | text | FK → `dim_category`. Natureza canônica. |
| `nature_name` | text | Rótulo de exibição. |
| `category_code` / `category_name` | text | `CVLI`, `CCP`, `OUTROS`, `PRODUTIVIDADE`. |
| `metric_type` | text | `CRIME` ou `POLICE_ACTIVITY`. **Nunca some os dois.** |
| `is_violent` | bool | Crime com violência ou grave ameaça. |
| `occurrences` | int | Ocorrências registradas. |
| `population_2022` | bigint | Denominador usado. |
| `population_reference_year` | int | Sempre `2022`. |
| `occurrences_per_10k` | numeric | Taxa por 10 mil habitantes. |
| `axis_source` | text | Eixo original da SSP, preservado para auditoria. |

---

## marts.fct_health_facility

Grão: `cnes_code` (um estabelecimento).

| Coluna | Tipo | Descrição |
|---|---|---|
| `cnes_code` | bigint | **PK.** |
| `region_id` | text | FK → `dim_region`. `NULL` quando não foi possível determinar. |
| `facility_name` | text | Nome fantasia. |
| `unit_type_code` / `unit_type_name` | int / text | Tipo de unidade, descrição oficial do CNES. |
| `service_group` | text | `HOSPITALAR`, `URGÊNCIA`, `DIAGNÓSTICO E TERAPIA`, `AMBULATORIAL`, `APOIO E GESTÃO`, `OUTROS`. Derivado da descrição oficial. |
| `sector` | text | `PÚBLICO`, `PRIVADO`, `SEM FINS LUCRATIVOS`. Derivado da **natureza jurídica**. |
| `legal_nature_group` | text | Grupo CONCLA/IBGE por extenso. |
| `management_sphere` | text | Esfera de gestão no SUS. **Não serve para separar público de privado.** |
| `serves_sus_ambulatory` | bool | Faz atendimento **ambulatorial** pelo SUS. |
| `has_hospital_care`, `has_surgery_center`, `has_obstetric_center`, `has_neonatal_center` | bool | Flags do CNES. Verdadeiros em poucos registros. |
| `latitude` / `longitude` | float | Coordenada do cadastro. |
| `region_assignment` | text | `OK` (coordenada), `INFERRED_NEIGHBORHOOD` (bairro), `UNRESOLVED`. |
| `neighborhood_agreement` | numeric | Concordância da inferência por bairro. |

---

## marts.fct_weather_daily

Grão: `region_id` × `observed_on`.

| Coluna | Tipo | Descrição |
|---|---|---|
| `region_id` | text | FK → `dim_region`. |
| `observed_on` | date | Dia. |
| `temp_max_c`, `temp_min_c`, `temp_mean_c` | float | Temperaturas (°C). |
| `precipitation_mm` | float | Acumulado do dia. |
| `humidity_mean_pct` | float | Umidade relativa média. |
| `wind_max_kmh` | float | Rajada máxima. |
| `is_rainy_day` | bool | `precipitation_mm >= 1,0` (convenção OMM). |
| `grid_lat` / `grid_lon` | float | Ponto efetivamente consultado no Open-Meteo. |
| `regions_sharing_cell` | int | Quantas RAs compartilham essa célula. `> 1` = série idêntica. |

---

## marts.mart_region_overview

Grão: `region_id`. Uma linha por RA com todos os indicadores de topo — é o que
a página de região e o mapa consomem.

Campos além de `dim_region`:

| Coluna | Descrição |
|---|---|
| `security_reference_year` | Último ano **completo** (12 meses) publicado para aquela RA. Varia entre regiões. |
| `crimes_total`, `cvli_total`, `property_crimes_total`, `violent_total` | Totais do ano de referência. |
| `police_activity_total` | Produtividade policial, contada à parte. |
| `crimes_per_10k`, `cvli_per_100k` | Taxas sobre o Censo 2022. |
| `health_facilities`, `health_facilities_public`, `health_facilities_sus_ambulatory`, `health_facilities_hospital`, `health_facilities_per_10k` | Rede instalada. |
| `temp_mean_c`, `temp_max_avg_c`, `temp_min_avg_c`, `precipitation_mm_per_year`, `rainy_days_per_year` | Normais do período disponível, só sobre meses fechados. |
| `weather_first_year`, `weather_last_year`, `weather_regions_sharing_cell` | Metadados do clima. |

---

## marts.mart_security_region_monthly

Grão: `region_id` × mês × `category_code`. Alimenta os gráficos temporais.

`crimes` e `produtividade policial` ficam em linhas separadas por
`metric_type`.

---

## marts.mart_weather_region_monthly

Grão: `region_id` × ano × mês.

| Coluna | Descrição |
|---|---|
| `days_observed` | **Menos de 28 = mês parcial.** O acumulado de chuva não é comparável ao de um mês fechado. |
| `temp_mean_c`, `temp_max_avg_c`, `temp_min_avg_c` | Médias do mês. |
| `temp_max_absolute_c`, `temp_min_absolute_c` | Extremos do mês. |
| `precipitation_mm`, `rainy_days` | Acumulado e contagem. |

---

## marts.mart_health_region

Grão: `region_id` (incluindo uma linha com `region_id` nulo, que agrupa os
estabelecimentos sem região determinada — eles **não** são distribuídos entre
as demais RAs).

---

## marts.mart_data_coverage

Grão: `region_id`. Existe para que lacuna apareça como lacuna.

| Coluna | Descrição |
|---|---|
| `population_2022_available`, `population_2010_available` | Censo publicado para essa RA. |
| `security_years_with_data` / `security_years_expected` | Cobertura da SSP-DF. |
| `security_missing_years` | int[] — anos sem publicação para essa RA. |
| `security_months_with_data` | Meses distintos com dado. |
| `health_facilities` | Estabelecimentos atribuídos. |
| `education_schools`, `education_years_with_enrollment` | Escolas no último Censo Escolar e anos com arquivo de matrículas completo. |
| `mobility_bikeway_km`, `mobility_metro_stations` | Malha cicloviária e estações de metrô na RA. |
| `weather_first_day`, `weather_last_day`, `weather_days` | Cobertura climática. |
| `domains_with_data` | 0 a 6 — quantos domínios publicados têm dado para essa RA. É o número que a malha da interface pinta. |
| `has_all_domains` | Tem dado nos quatro domínios de série longa (população, segurança, saúde, clima). |

---

## marts.mart_insights

Grão: `insight_id`. Achados calculados — nenhum texto é redigido à mão.

| Coluna | Descrição |
|---|---|
| `domain` | `population`, `security`, `health`, `weather`, `quality`. |
| `title` / `finding` | Título e texto, gerados a partir dos dados. |
| `value_numeric` / `unit` | Valor principal e unidade. |
| `period_start` / `period_end` | Período coberto pelo achado. |
| `method` | Como o número foi calculado. **Obrigatório.** |
| `source_id` | FK → `dim_source`. |
| `caveat` | Limitação metodológica. |

---

## marts.mart_pipeline_status

Grão: `source_key`. Última execução de cada fonte — alimenta o KPI "última
atualização" e a página de transparência.

---

## meta.ingestion_run / meta.data_quality_check

`ingestion_run`: `run_id`, `source_key`, `started_at`, `finished_at`, `status`
(`RUNNING` / `SUCCESS` / `FAILED`), `rows_written`, `requests_made`,
`error_message`.

`data_quality_check`: `check_id`, `run_id`, `check_name`, `severity`
(`INFO` / `WARN` / `ERROR`), `passed`, `observed`, `expected`, `checked_at`.
