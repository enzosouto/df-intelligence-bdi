{#
  Dá à role de leitura da API acesso ao que ela lê: o schema `marts`.

  Em produção a API conecta com uma role só de leitura (`api_reader`), e não
  com a dona das tabelas. Como o dbt recria cada tabela do `marts` a cada
  execução, o GRANT da tabela precisa ser refeito junto — por isso é post-hook
  do próprio modelo, e o acesso volta no mesmo instante em que a tabela nova
  entra no ar.

  O USAGE do schema vai uma vez só, no on-run-start: dado em cada post-hook,
  as threads do dbt disputam a mesma linha do catálogo e o Postgres recusa
  com "tuple concurrently updated".

  Sem a role (Docker local, CI), não faz nada.
#}
{% macro _if_api_reader(statement) %}
  {% set role = env_var('API_READER_ROLE', 'api_reader') %}
  do $grant$
  begin
    if exists (select 1 from pg_roles where rolname = '{{ role }}') then
      execute '{{ statement | replace("ROLE", role) }}';
    end if;
  end
  $grant$;
{% endmacro %}

{% macro grant_api_reader_schema() %}
  {{ _if_api_reader('create schema if not exists marts; grant usage on schema marts to ROLE') }}
{% endmacro %}

{# Fim da execução: cobre as tabelas que não foram recriadas nesta rodada (um
   teste que falha faz o dbt pular o que vem depois, e a tabela antiga fica). #}
{% macro grant_api_reader_all() %}
  {{ _if_api_reader('grant select on all tables in schema marts to ROLE') }}
{% endmacro %}

{% macro grant_api_reader() %}
  {{ _if_api_reader('grant select on ' ~ this ~ ' to ROLE') }}
{% endmacro %}
