{#
  Normaliza nome de região para comparação entre fontes: sem acento, maiúsculo,
  `/` vira espaço, espaços repetidos colapsam, sem espaço nas pontas.
  `'AGUAS CLARAS '` (SEEDF 2025) e `'ÁGUAS CLARAS'` (GDF) viram o mesmo texto.
  Espelha `ingestion.education.norm`.
#}
{% macro norm_name(column) -%}
    upper(regexp_replace(trim(translate(replace({{ column }}, '/', ' '),
        'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇáàâãäéèêëíìîïóòôõöúùûüç',
        'AAAAAEEEEIIIIOOOOOUUUUCaaaaaeeeeiiiiooooouuuuc')), '\s+', ' ', 'g'))
{%- endmacro %}
