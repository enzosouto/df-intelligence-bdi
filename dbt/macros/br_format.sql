{#
    Formatação numérica pt-BR, independente de locale do banco.

    `to_char` com os padrões `G`/`D` usa o locale do servidor — o que produziria
    "1,006" num Postgres em locale C e "1.006" num em pt_BR. Como o texto dos
    insights é gravado no banco e servido direto para a interface, a formatação
    precisa ser determinística.

    Aqui os separadores são inseridos explicitamente: `.` para milhar (via
    lookahead, suportado pela engine de regex do Postgres) e `,` para decimal.
#}

{% macro br_int(expression) -%}
    regexp_replace(round(({{ expression }})::numeric)::bigint::text,
                   '(\d)(?=(\d{3})+$)', '\1.', 'g')
{%- endmacro %}


{% macro br_decimal(expression, decimals=1) -%}
{%- if decimals == 0 -%}
    {{ br_int(expression) }}
{%- else -%}
    replace(
        replace(
            regexp_replace(
                to_char(round(({{ expression }})::numeric, {{ decimals }}),
                        'FM9999999990.{{ "0" * decimals }}'),
                '(\d)(?=(\d{3})+\.)', '\1@', 'g'
            ),
            '.', ','
        ),
        '@', '.'
    )
{%- endif -%}
{%- endmacro %}
