/*
  A SSP-DF muda o conjunto de naturezas criminais entre anos — `ESTUPRO DE
  VULNERÁVEL` só aparece a partir de 2019, por exemplo.

  `stg_security_occurrences` faz INNER JOIN com o seed de naturezas, ou seja:
  uma natureza nova seria descartada em silêncio. Este teste torna esse
  silêncio impossível — se a fonte publicar um tipo criminal que o projeto não
  conhece, o pipeline falha e alguém precisa decidir conscientemente em que
  categoria ele entra.
*/

select
    nature_source,
    min(reference_year) as first_seen_year,
    max(reference_year) as last_seen_year,
    sum(occurrences)    as total_occurrences
from {{ source('raw', 'security_occurrence') }}
where nature_source not in (select nature_source from {{ ref('security_nature_map') }})
group by nature_source
