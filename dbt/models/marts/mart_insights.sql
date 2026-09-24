/*
  Insights calculados a partir dos dados — não redigidos à mão.

  Cada linha carrega: o achado, o número, o período, o método de cálculo, a
  fonte e a ressalva. Se o dado mudar, o texto muda junto; se o dado sumir, o
  insight some em vez de virar afirmação órfã.

  DUAS REGRAS EDITORIAIS APLICADAS AQUI

  1. Nenhum insight afirma causa. Variações são descritas como variações. Onde
     duas séries se movem juntas, o texto diz "associação" e a ressalva diz
     explicitamente que correlação não implica causalidade.

  2. Nenhuma comparação temporal mistura recortes diferentes. A cobertura da
     SSP-DF varia por ano e por RA: comparar "o total de 2014" com "o total de
     2026" seria comparar 29 RAs com 12 meses contra 31 RAs com 8 meses. Todas
     as séries agregadas do DF aqui são restritas a anos COMPLETOS (12 meses) e
     ao conjunto de RAs presente nos DOIS extremos do intervalo.
*/

with df_population as (
    select * from {{ ref('fct_population_df') }}
),

population_span as (
    select
        min(reference_year) as first_year,
        max(reference_year) as last_year,
        (select population from df_population
          where reference_year = (select min(reference_year) from df_population)) as first_population,
        (select population from df_population
          where reference_year = (select max(reference_year) from df_population)) as last_population
    from df_population
),

territorial_redefinition as (
    select
        count(*) filter (where existed_in_2010)                                as regions_in_2010,
        count(*) filter (where not existed_in_2010)                            as regions_created_after,
        count(*) filter (where existed_in_2010 and lost_territory_after_2010)  as regions_that_lost_territory,
        count(*) filter (where is_growth_comparable)                           as comparable_regions,
        count(*)                                                               as total_regions
    from {{ ref('dim_region') }}
),

biggest_apparent_drop as (
    select region_name, population_2010, population_2022,
           round(100.0 * (population_2022 - population_2010) / population_2010, 1) as apparent_pct
    from {{ ref('dim_region') }}
    where existed_in_2010 and population_2010 > 0 and population_2022 is not null
    order by (population_2022 - population_2010)::numeric / population_2010 asc
    limit 1
),

densest as (
    select region_name, density_2022_per_km2
    from {{ ref('dim_region') }}
    where density_2022_per_km2 is not null
    order by density_2022_per_km2 desc
    limit 1
),

-- ---------------------------------------------------------------------------
-- Base comparável de segurança
-- ---------------------------------------------------------------------------
region_year_completeness as (
    select region_id, reference_year, count(distinct reference_month) as months
    from {{ ref('fct_security_monthly') }}
    group by region_id, reference_year
),

complete_region_years as (
    select region_id, reference_year
    from region_year_completeness
    where months = 12
),

usable_years as (
    -- Anos em que a maior parte do DF publicou os 12 meses.
    select reference_year
    from complete_region_years
    group by reference_year
    having count(distinct region_id) >= 29
),

security_span as (
    select min(reference_year) as first_year, max(reference_year) as last_year
    from usable_years
),

-- Só as RAs que fecharam 12 meses NOS DOIS extremos entram na comparação.
panel_regions as (
    select first_year_data.region_id
    from complete_region_years as first_year_data
    inner join security_span as span on first_year_data.reference_year = span.first_year
    inner join complete_region_years as last_year_data
        on last_year_data.region_id = first_year_data.region_id
    inner join security_span as span2 on last_year_data.reference_year = span2.last_year
),

security_endpoints as (
    select
        span.first_year,
        span.last_year,
        (select count(*) from panel_regions) as panel_size,
        sum(facts.occurrences) filter (
            where facts.reference_year = span.first_year and facts.metric_type = 'CRIME') as first_crimes,
        sum(facts.occurrences) filter (
            where facts.reference_year = span.last_year  and facts.metric_type = 'CRIME') as last_crimes,
        sum(facts.occurrences) filter (
            where facts.reference_year = span.first_year and facts.category_code = 'CVLI') as first_cvli,
        sum(facts.occurrences) filter (
            where facts.reference_year = span.last_year  and facts.category_code = 'CVLI') as last_cvli
    from {{ ref('fct_security_monthly') }} as facts
    cross join security_span as span
    where facts.region_id in (select region_id from panel_regions)
      and facts.reference_year in (span.first_year, span.last_year)
    group by span.first_year, span.last_year
),

-- Extremos de taxa, comparando apenas RAs de porte semelhante. RAs com menos
-- de 20 mil habitantes produzem taxas instáveis e, no caso de áreas
-- industriais e comerciais, fisicamente enganosas.
rate_candidates as (
    select region_name, crimes_per_10k, security_reference_year, population_2022
    from {{ ref('mart_region_overview') }}
    where crimes_per_10k is not null and population_2022 >= 20000
),

highest_crime_rate as (
    select * from rate_candidates order by crimes_per_10k desc limit 1
),

lowest_crime_rate as (
    select * from rate_candidates order by crimes_per_10k asc limit 1
),

-- ---------------------------------------------------------------------------
-- Saúde
-- ---------------------------------------------------------------------------
health_totals as (
    select
        sum(facilities_total)                                     as facilities_all,
        sum(facilities_total) filter (where region_id is not null) as facilities_located
    from {{ ref('mart_health_region') }}
),

health_concentration as (
    select
        overview.region_name,
        overview.health_facilities,
        round(100.0 * overview.health_facilities
              / nullif((select facilities_located from health_totals), 0), 1) as share_pct
    from {{ ref('mart_region_overview') }} as overview
    order by overview.health_facilities desc
    limit 1
),

health_access_gap as (
    select
        min(health_facilities_per_10k) as min_rate,
        max(health_facilities_per_10k) as max_rate,
        (array_agg(region_name order by health_facilities_per_10k asc))[1]  as lowest_region,
        (array_agg(region_name order by health_facilities_per_10k desc))[1] as highest_region
    from {{ ref('mart_region_overview') }}
    where health_facilities_per_10k is not null and population_2022 >= 20000
),

-- ---------------------------------------------------------------------------
-- Clima e qualidade
-- ---------------------------------------------------------------------------
weather_seasonality as (
    select
        round(avg(precipitation_mm) filter (where reference_month between 5 and 9), 1)     as dry_season_mm,
        round(avg(precipitation_mm) filter (where reference_month not between 5 and 9), 1) as wet_season_mm,
        min(reference_year) as first_year,
        max(reference_year) as last_year
    from {{ ref('mart_weather_region_monthly') }}
    where days_observed >= 28
),

coverage_gap as (
    select
        count(*) filter (where 2024 = any(security_missing_years)) as regions_missing_2024,
        count(*)                                                   as total_regions
    from {{ ref('mart_data_coverage') }}
),

-- ---------------------------------------------------------------------------
-- Educação
-- ---------------------------------------------------------------------------
education_df as (
    select * from {{ ref('mart_education_yearly') }}
    where scope = 'DF' and is_year_complete and enrollment_total is not null
),

education_span as (
    select
        first_year.census_year        as first_year,
        last_year.census_year         as last_year,
        first_year.enrollment_total   as first_total,
        last_year.enrollment_total    as last_total,
        first_year.early_childhood    as first_early,
        last_year.early_childhood     as last_early,
        last_year.enrollment_public_share_pct as last_public_share
    from (select * from education_df order by census_year asc  limit 1) as first_year
    cross join (select * from education_df order by census_year desc limit 1) as last_year
    where first_year.census_year < last_year.census_year
),

education_year_coverage as (
    select
        census_year,
        bool_and(is_complete)                                                   as is_complete,
        sum(schools_in_enrollment_file)::numeric / nullif(sum(schools_in_registry), 0) as coverage
    from {{ ref('mart_education_coverage') }}
    group by census_year
),

education_gaps as (
    select
        string_agg(census_year::text, ', ' order by census_year)  as incomplete_years,
        min(coverage)                                             as worst_coverage,
        min(census_year)                                          as first_gap_year,
        max(census_year)                                          as last_gap_year
    from education_year_coverage
    where not is_complete
),

insights as (

    select
        'POP_DF_SPAN'                                   as insight_id,
        'population'                                    as domain,
        'População do Distrito Federal'                 as title,
        format(
            'Entre %s e %s, a população estimada do DF passou de %s para %s habitantes — variação de %s%%.',
            first_year, last_year,
            {{ br_int('first_population') }},
            {{ br_int('last_population') }},
            {{ br_decimal('100.0 * (last_population - first_population) / first_population', 1) }}
        )                                               as finding,
        round(100.0 * (last_population - first_population) / first_population, 2) as value_numeric,
        '%'                                             as unit,
        first_year                                      as period_start,
        last_year                                       as period_end,
        'Diferença percentual entre o primeiro e o último ano da série de estimativas do IBGE (agregado 6579).' as method,
        'IBGE_ESTIMATIVAS'                              as source_id,
        'A série tem lacunas em anos de Censo e de revisão metodológica; esses anos não foram interpolados. Os anos finais são projeção, não contagem.' as caveat
    from population_span

    union all

    select
        'POP_RA_NOT_COMPARABLE',
        'population',
        'Por que não há ranking de crescimento populacional por região',
        format(
            'Nenhuma das %s Regiões Administrativas permite comparar diretamente os Censos de 2010 e 2022: das %s que existiam em 2010, todas as %s cederam território às %s RAs criadas no período. Exemplo: %s aparenta ter encolhido %s%% (de %s para %s habitantes), mas isso é redefinição de limite, não perda de moradores.',
            redefinition.total_regions,
            redefinition.regions_in_2010,
            redefinition.regions_that_lost_territory,
            redefinition.regions_created_after,
            drop_example.region_name,
            {{ br_decimal('abs(drop_example.apparent_pct)', 1) }},
            {{ br_int('drop_example.population_2010') }},
            {{ br_int('drop_example.population_2022') }}
        ),
        redefinition.regions_created_after,
        'RAs criadas',
        2010,
        2022,
        'Uma RA só seria comparável entre os Censos se existisse em 2010 e não fizesse fronteira com nenhuma RA criada depois. Verificando a malha oficial de 2025 contra os subdistritos do Censo 2010, nenhuma RA satisfaz as duas condições.',
        'IBGE_CENSO_2022',
        'Reconstruir o território comparável exigiria a malha de subdistritos do IBGE de 2010, que a API de malhas não disponibiliza. O crescimento do DF como um todo continua válido e está no indicador de população do Distrito Federal.'
    from territorial_redefinition as redefinition
    cross join biggest_apparent_drop as drop_example

    union all

    select
        'POP_DENSEST',
        'population',
        'Região mais densa',
        format(
            '%s é a Região Administrativa mais densa do DF: %s habitantes por km² no Censo 2022.',
            region_name,
            {{ br_decimal('density_2022_per_km2', 0) }}
        ),
        density_2022_per_km2,
        'hab/km²',
        2022,
        2022,
        'População do Censo 2022 dividida pela área geodésica do polígono oficial da RA (IBRAM/ONDA-DF 2025).',
        'IBGE_CENSO_2022',
        'A área inclui zonas rurais e de preservação dentro do limite da RA, o que reduz a densidade de regiões extensas.'
    from densest

    union all

    select
        'SEC_DF_TREND',
        'security',
        'Evolução dos crimes registrados',
        format(
            'Entre %s e %s, nas %s Regiões Administrativas com série completa em ambos os anos, os crimes registrados passaram de %s para %s — variação de %s%%.',
            first_year, last_year, panel_size,
            {{ br_int('first_crimes') }},
            {{ br_int('last_crimes') }},
            {{ br_decimal('100.0 * (last_crimes - first_crimes) / nullif(first_crimes, 0)', 1) }}
        ),
        round(100.0 * (last_crimes - first_crimes) / nullif(first_crimes, 0), 2),
        '%',
        first_year,
        last_year,
        format(
            'Soma das naturezas classificadas como CRIME (exclui produtividade policial), nas %s RAs que publicaram os 12 meses tanto em %s quanto em %s. Anos incompletos e RAs presentes em apenas um dos extremos foram excluídos.',
            panel_size, first_year, last_year
        ),
        'SSP_DF_BALANCO',
        'São registros de ocorrência policial, não a totalidade dos crimes. Parte da variação pode refletir mudança no comportamento de registro, e não apenas na ocorrência dos fatos.'
    from security_endpoints

    union all

    select
        'SEC_CVLI_TREND',
        'security',
        'Crimes Violentos Letais Intencionais (CVLI)',
        format(
            'Nas mesmas %s Regiões Administrativas, os CVLI passaram de %s em %s para %s em %s — variação de %s%%.',
            panel_size,
            {{ br_int('first_cvli') }}, first_year,
            {{ br_int('last_cvli') }},  last_year,
            {{ br_decimal('100.0 * (last_cvli - first_cvli) / nullif(first_cvli, 0)', 1) }}
        ),
        round(100.0 * (last_cvli - first_cvli) / nullif(first_cvli, 0), 2),
        '%',
        first_year,
        last_year,
        'Soma de homicídio, latrocínio e lesão corporal seguida de morte, no mesmo painel de RAs e anos completos usado no indicador geral.',
        'SSP_DF_BALANCO',
        'CVLI é o indicador criminal menos sujeito a subnotificação, porque envolve morte e perícia — mas ainda assim reflete registro policial.'
    from security_endpoints

    union all

    select
        'SEC_RATE_SPREAD',
        'security',
        'Diferença entre regiões na taxa de criminalidade',
        format(
            'Normalizando pela população, %s registrou %s crimes por 10 mil habitantes em %s, enquanto %s registrou %s — uma diferença de %s vezes.',
            highest.region_name, {{ br_decimal('highest.crimes_per_10k', 1) }}, highest.security_reference_year,
            lowest.region_name,  {{ br_decimal('lowest.crimes_per_10k', 1) }},
            {{ br_decimal('highest.crimes_per_10k / nullif(lowest.crimes_per_10k, 0)', 1) }}
        ),
        round(highest.crimes_per_10k / nullif(lowest.crimes_per_10k, 0), 2),
        'x',
        lowest.security_reference_year,
        highest.security_reference_year,
        'Crimes do último ano completo de cada RA divididos pela população do Censo 2022, restrito a RAs com pelo menos 20 mil habitantes — abaixo disso a taxa fica instável.',
        'SSP_DF_BALANCO',
        'Regiões com grande fluxo diário de não residentes têm taxa inflada: o denominador é população residente, mas o numerador inclui crimes contra visitantes. A diferença descreve o registro, não explica a causa — correlação não implica causalidade.'
    from highest_crime_rate as highest
    cross join lowest_crime_rate as lowest

    union all

    select
        'HEALTH_CONCENTRATION',
        'health',
        'Concentração da rede de saúde',
        format(
            '%s concentra %s dos %s estabelecimentos de saúde do CNES que foi possível localizar em uma Região Administrativa — %s%% do total localizado.',
            concentration.region_name,
            {{ br_int('concentration.health_facilities') }},
            {{ br_int('totals.facilities_located') }},
            {{ br_decimal('concentration.share_pct', 1) }}
        ),
        concentration.share_pct,
        '%',
        extract(year from current_date)::int,
        extract(year from current_date)::int,
        format(
            'Estabelecimentos do CNES atribuídos a cada RA por coordenada geográfica ou, na ausência dela, pelo bairro informado quando há evidência suficiente. De %s registros no DF, %s foram localizados.',
            {{ br_int('totals.facilities_all') }},
            {{ br_int('totals.facilities_located') }}
        ),
        'CNES_ESTABELECIMENTOS',
        'É infraestrutura cadastrada, não produção de atendimentos. A maioria dos registros são consultórios e clínicas privadas, o que desloca a distribuição para as regiões de maior renda.'
    from health_concentration as concentration
    cross join health_totals as totals

    union all

    select
        'HEALTH_ACCESS_GAP',
        'health',
        'Desigualdade na oferta instalada de saúde',
        format(
            'A oferta instalada varia de %s estabelecimentos por 10 mil habitantes em %s a %s em %s.',
            {{ br_decimal('min_rate', 1) }}, lowest_region,
            {{ br_decimal('max_rate', 1) }}, highest_region
        ),
        round(max_rate / nullif(min_rate, 0), 2),
        'x',
        extract(year from current_date)::int,
        extract(year from current_date)::int,
        'Estabelecimentos do CNES por RA divididos pela população do Censo 2022, restrito a RAs com pelo menos 20 mil habitantes.',
        'CNES_ESTABELECIMENTOS',
        'Moradores se deslocam entre RAs para se tratar: oferta instalada na região não equivale a acesso da população da região.'
    from health_access_gap

    union all

    select
        'WEATHER_SEASONALITY',
        'weather',
        'Sazonalidade da chuva no Planalto Central',
        format(
            'Entre %s e %s, a média mensal de chuva foi de %s mm na estação chuvosa (outubro a abril) contra %s mm na estação seca (maio a setembro).',
            first_year, last_year,
            {{ br_decimal('wet_season_mm', 1) }},
            {{ br_decimal('dry_season_mm', 1) }}
        ),
        round(wet_season_mm / nullif(dry_season_mm, 0), 1),
        'x',
        first_year,
        last_year,
        'Média da precipitação mensal acumulada por RA, separando maio–setembro (seca) dos demais meses, considerando apenas meses com 28 dias ou mais de observação.',
        'OPEN_METEO_ERA5',
        'Fonte não governamental: reanálise ERA5 interpolada, não medição de estação do INMET.'
    from weather_seasonality

    union all

    select
        'EDU_ENROLLMENT_TREND',
        'education',
        'Matrículas na educação básica do DF',
        format(
            'Entre %s e %s, as matrículas de escolarização no DF, somando todas as redes, passaram de %s para %s — variação de %s%%. Na educação infantil (creche e pré-escola), o movimento foi de %s para %s (%s%%).',
            first_year, last_year,
            {{ br_int('first_total') }}, {{ br_int('last_total') }},
            {{ br_decimal('100.0 * (last_total - first_total) / nullif(first_total, 0)', 1) }},
            {{ br_int('first_early') }}, {{ br_int('last_early') }},
            {{ br_decimal('100.0 * (last_early - first_early) / nullif(first_early, 0)', 1) }}
        ),
        round(100.0 * (last_total - first_total) / nullif(first_total, 0), 2),
        '%',
        first_year,
        last_year,
        'Soma do total de matrículas publicado pela SEEDF para cada escola, em anos cujo arquivo de matrículas cobre ao menos 95% das escolas do cadastro em todas as redes.',
        'SEEDF_EDUCACENSO',
        'A variação descreve matrículas registradas, não população em idade escolar. Anos com arquivo incompleto ou sem total publicado ficam fora da comparação.'
    from education_span

    union all

    select
        'EDU_PUBLIC_SHARE',
        'education',
        'Peso da rede pública',
        format(
            'Em %s, %s%% das matrículas de escolarização do DF estavam na rede pública (distrital e federal). O restante se divide entre escolas particulares e particulares conveniadas com o GDF.',
            last_year, {{ br_decimal('last_public_share', 1) }}
        ),
        last_public_share,
        '%',
        last_year,
        last_year,
        'Matrículas em escolas das redes 1 (federal), 2 (SEEDF) e 5 (pública não vinculada à SEEDF) divididas pelo total de matrículas publicado.',
        'SEEDF_EDUCACENSO',
        'Escolas conveniadas são privadas com vagas custeadas pelo GDF — sobretudo creches — e não entram na rede pública aqui.'
    from education_span

    union all

    select
        'EDU_ENROLLMENT_FILE_GAP',
        'quality',
        'Arquivo de matrículas incompleto',
        format(
            'O arquivo de matrículas publicado pela SEEDF para %s cobre apenas %s%% das escolas do cadastro do mesmo ano. As matrículas desse ano não são exibidas: somá-las mostraria uma queda que não aconteceu.',
            incomplete_years, {{ br_decimal('100.0 * worst_coverage', 0) }}
        ),
        round(100.0 * worst_coverage, 1),
        '%',
        first_gap_year,
        last_gap_year,
        'Fração das escolas do cadastro de unidades escolares presentes no arquivo de matrículas do mesmo ano, por rede. Abaixo de 95% o ano não é publicado.',
        'SEEDF_EDUCACENSO',
        'Ausência de dado não é ausência de aluno. O número de escolas continua disponível, porque o cadastro está completo.'
    from education_gaps
    where incomplete_years is not null

    union all

    select
        'COVERAGE_2024_GAP',
        'quality',
        'Lacuna de publicação nos dados de segurança',
        format(
            'A SSP-DF não publica o balanço criminal de 2024 para %s das %s Regiões Administrativas: na página oficial, os links desse ano apontam para arquivos de outros anos.',
            regions_missing_2024, total_regions
        ),
        regions_missing_2024,
        'RAs',
        2024,
        2024,
        'Contagem de RAs sem nenhum registro de 2024 após processar todas as planilhas publicadas na página de dados por RA da SSP-DF.',
        'SSP_DF_BALANCO',
        'Ausência de dado não é ausência de ocorrência. Esses casos aparecem como lacuna na interface, nunca como zero.'
    from coverage_gap
    where regions_missing_2024 > 0
)

select * from insights
