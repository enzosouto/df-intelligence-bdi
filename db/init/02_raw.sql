-- ---------------------------------------------------------------------------
-- Camada RAW
--
-- Regra: uma tabela por recurso de fonte. Nenhuma regra de negócio aqui.
-- Toda tabela tem chave natural + PRIMARY KEY para que a carga seja um UPSERT
-- idempotente (rodar de novo não duplica nem corrompe).
--
-- `_ingested_at` e `_source_url` existem em toda tabela para rastreabilidade:
-- qualquer número do dashboard consegue ser rastreado até a requisição que o
-- trouxe.
-- ---------------------------------------------------------------------------

-- Geometria oficial das Regiões Administrativas (IBRAM / ONDA-DF, 2025) ------
CREATE TABLE IF NOT EXISTS raw.region_geo (
    ra_code         text PRIMARY KEY,          -- "RA-I" ... "RA-XXXV"
    ra_cira         integer NOT NULL,          -- código numérico da RA
    ra_name_source  text    NOT NULL,          -- nome como vem da fonte (CAIXA ALTA)
    ra_monograph_url text,
    area_km2        double precision NOT NULL, -- geodésica, calculada do polígono
    centroid_lat    double precision NOT NULL,
    centroid_lon    double precision NOT NULL,
    bbox_min_lon    double precision NOT NULL,
    bbox_min_lat    double precision NOT NULL,
    bbox_max_lon    double precision NOT NULL,
    bbox_max_lat    double precision NOT NULL,
    geometry        jsonb NOT NULL,            -- GeoJSON geometry (WGS84)
    -- Vizinhança calculada do próprio polígono: [{"ra_code": "...", "shared_km": 12.3}, ...]
    -- ordenada por extensão de fronteira compartilhada. Usada pelo dbt para
    -- inferir de qual RA cada RA criada após 2010 foi desmembrada.
    neighbors       jsonb NOT NULL DEFAULT '[]'::jsonb,
    _source_url     text NOT NULL,
    _ingested_at    timestamptz NOT NULL DEFAULT now()
);

-- Subdistritos IBGE de Brasília (= Regiões Administrativas) ------------------
CREATE TABLE IF NOT EXISTS raw.ibge_subdistrict (
    subdistrict_id  bigint PRIMARY KEY,        -- 53001080506 ...
    subdistrict_name text NOT NULL,
    district_id     bigint NOT NULL,
    municipality_id integer NOT NULL,
    _source_url     text NOT NULL,
    _ingested_at    timestamptz NOT NULL DEFAULT now()
);

-- População por subdistrito (Censos IBGE 2010 e 2022) ------------------------
CREATE TABLE IF NOT EXISTS raw.population_census (
    subdistrict_id  bigint  NOT NULL,
    census_year     integer NOT NULL,
    population      bigint  NOT NULL,
    ibge_aggregate  integer NOT NULL,          -- 1309 (2010) / 9923 (2022)
    _source_url     text NOT NULL,
    _ingested_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (subdistrict_id, census_year)
);

-- População estimada do DF (IBGE, série anual) -------------------------------
CREATE TABLE IF NOT EXISTS raw.population_df_estimate (
    reference_year  integer PRIMARY KEY,
    population      bigint  NOT NULL,
    _source_url     text NOT NULL,
    _ingested_at    timestamptz NOT NULL DEFAULT now()
);

-- Balanço criminal mensal por RA (SSP-DF) ------------------------------------
-- Chave natural: RA + ano + mês + natureza. O ano vem de DENTRO do arquivo,
-- nunca do link (os slugs do portal se repetem entre anos).
CREATE TABLE IF NOT EXISTS raw.security_occurrence (
    ra_code         text    NOT NULL,          -- "RA-XX" lido do cabeçalho da planilha
    reference_year  integer NOT NULL,
    reference_month integer NOT NULL CHECK (reference_month BETWEEN 1 AND 12),
    axis_source     text    NOT NULL,          -- "1. C.V.L.I. - ..." etc.
    nature_source   text    NOT NULL,          -- "HOMICÍDIO", "ROUBO DE VEÍCULO" ...
    occurrences     integer NOT NULL CHECK (occurrences >= 0),
    ra_label_source text    NOT NULL,          -- linha 4 da planilha, na íntegra
    _source_url     text NOT NULL,
    _ingested_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ra_code, reference_year, reference_month, nature_source)
);

-- Estabelecimentos de saúde (CNES / Ministério da Saúde) ---------------------
CREATE TABLE IF NOT EXISTS raw.health_facility (
    cnes_code       bigint PRIMARY KEY,
    trade_name      text,
    legal_name      text,
    unit_type_code  integer,
    admin_sphere    text,
    management_type text,
    neighborhood    text,
    postal_code     text,
    latitude        double precision,
    longitude       double precision,
    has_surgery_center     boolean,
    has_obstetric_center   boolean,
    has_neonatal_center    boolean,
    has_hospital_care      boolean,
    has_ambulatory_care    boolean,
    serves_sus_ambulatory  boolean,
    shift_description      text,
    source_updated_at      text,
    -- atribuição espacial feita na ingestão (point-in-polygon contra raw.region_geo)
    ra_code         text,
    geocode_quality text NOT NULL DEFAULT 'UNKNOWN'
        CHECK (geocode_quality IN ('OK', 'LOW', 'MISSING', 'OUTSIDE_DF', 'UNKNOWN')),
    _source_url     text NOT NULL,
    _ingested_at    timestamptz NOT NULL DEFAULT now()
);

-- Tabela de domínio dos tipos de unidade do CNES -----------------------------
-- Vem da própria API (/cnes/tipounidades). Não é lista digitada à mão.
CREATE TABLE IF NOT EXISTS raw.health_unit_type (
    unit_type_code  integer PRIMARY KEY,
    description     text NOT NULL,
    _source_url     text NOT NULL,
    _ingested_at    timestamptz NOT NULL DEFAULT now()
);

-- Clima diário por centroide de RA (Open-Meteo / ERA5) -----------------------
CREATE TABLE IF NOT EXISTS raw.weather_daily (
    ra_code         text NOT NULL,
    observed_on     date NOT NULL,
    temp_max_c      double precision,
    temp_min_c      double precision,
    temp_mean_c     double precision,
    precipitation_mm double precision,
    humidity_mean_pct double precision,
    wind_max_kmh    double precision,
    _source_url     text NOT NULL,
    _ingested_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ra_code, observed_on)
);

-- Migrações aditivas -------------------------------------------------------
-- `CREATE TABLE IF NOT EXISTS` não altera tabela já existente. Colunas novas
-- entram aqui para que o mesmo DDL sirva tanto para banco vazio quanto para
-- banco em uso.
ALTER TABLE raw.region_geo
    ADD COLUMN IF NOT EXISTS neighbors jsonb NOT NULL DEFAULT '[]'::jsonb;

-- Coordenada efetivamente consultada no Open-Meteo. RAs que caem na mesma
-- célula de amostragem compartilham a série — é o mesmo ponto de grade, e a
-- interface precisa poder dizer isso.
ALTER TABLE raw.weather_daily
    ADD COLUMN IF NOT EXISTS grid_lat double precision,
    ADD COLUMN IF NOT EXISTS grid_lon double precision;

-- Código de natureza jurídica (tabela CONCLA/IBGE). No CNES este é o campo que
-- separa público de privado de verdade — `descricao_esfera_administrativa`
-- informa quem GERENCIA, e no DF é "ESTADUAL" para quase tudo, inclusive
-- consultórios particulares.
ALTER TABLE raw.health_facility
    ADD COLUMN IF NOT EXISTS legal_nature_code text;

-- Perímetro geodésico da RA. Permite medir a fronteira compartilhada como
-- FRAÇÃO do próprio contorno, e não em quilômetros absolutos — senão uma RA
-- grande e irregular (Plano Piloto) "ganha" a vizinhança de todo mundo.
ALTER TABLE raw.region_geo
    ADD COLUMN IF NOT EXISTS perimeter_km double precision;

CREATE INDEX IF NOT EXISTS ix_security_ra_year  ON raw.security_occurrence (ra_code, reference_year);
CREATE INDEX IF NOT EXISTS ix_weather_ra_date   ON raw.weather_daily (ra_code, observed_on);
CREATE INDEX IF NOT EXISTS ix_health_ra         ON raw.health_facility (ra_code);
