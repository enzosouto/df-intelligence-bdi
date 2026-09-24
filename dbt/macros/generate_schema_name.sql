{#
    Por padrão o dbt concatena o schema do profile com o schema do modelo
    (staging + marts = staging_marts). Aqui os schemas são fixos e fazem parte
    do contrato com a API, então o nome customizado vale como está.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
