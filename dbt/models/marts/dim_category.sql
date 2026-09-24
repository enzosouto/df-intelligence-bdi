/*
  Dimensão de categorias, transversal aos domínios.

  Existe porque "categoria" significa coisas diferentes em cada fonte — natureza
  criminal na SSP, tipo de unidade no CNES — e a API precisa de uma única forma
  de listar "o que dá para filtrar" sem que o frontend conheça o esquema de
  cada fonte.
*/

with security_natures as (
    select distinct
        'SECURITY'              as domain,
        nature_key              as category_id,
        nature_name             as category_name,
        category_code           as parent_code,
        category_name           as parent_name,
        metric_type             as metric_type,
        is_violent              as is_violent
    from {{ ref('security_nature_map') }}
),

health_groups as (
    select distinct
        'HEALTH'                as domain,
        service_group           as category_id,
        initcap(service_group)  as category_name,
        'CNES'                  as parent_code,
        'Estabelecimentos de saúde (CNES)' as parent_name,
        'INFRASTRUCTURE'        as metric_type,
        null::boolean           as is_violent
    from {{ ref('stg_health_facilities') }}
)

select * from security_natures
union all
select * from health_groups
