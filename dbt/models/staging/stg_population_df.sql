/*
  Série anual de população do DF (IBGE).

  Anos de Censo e de revisão metodológica não têm estimativa publicada. As
  lacunas são preservadas como ausência de linha — interpolar aqui seria
  inventar dado.
*/

select
    reference_year,
    population,
    _source_url as source_url
from {{ source('raw', 'population_df_estimate') }}
