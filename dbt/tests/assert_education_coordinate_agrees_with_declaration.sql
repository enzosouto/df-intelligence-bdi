{{ config(severity = 'warn') }}
/*
  Onde a escola tem as duas evidências — coordenada e RA declarada coerente
  (código e nome batendo) —, elas precisam concordar na grande maioria dos
  casos. Discordância em massa indicaria coordenada trocada ou malha errada.
  Aviso, não erro: escolas na divisa entre RAs discordam legitimamente.
*/

select
    count(*) filter (where coordinate_agrees_with_declaration)     as agree,
    count(*) filter (where not coordinate_agrees_with_declaration) as disagree
from {{ ref('int_education_school_region') }}
having count(*) filter (where not coordinate_agrees_with_declaration)
     > 0.1 * count(*) filter (where coordinate_agrees_with_declaration is not null)
