/*
  Catálogo de fontes. Cada número exibido no produto consegue apontar para a
  linha desta tabela — órgão, URL, periodicidade e ressalva metodológica.
*/

select
    source_id,
    source_name,
    organization,
    domain,
    url,
    access_type,
    granularity,
    update_frequency,
    is_df_government,
    temporal_coverage,
    caveat
from {{ ref('source_catalog') }}
