/*
  Calendário do projeto. Começa em 2014-01-01 (primeiro ano do Balanço Criminal
  da SSP-DF) e vai até o fim do ano corrente.
*/

with days as (
    select generate_series(
        date '2014-01-01',
        date_trunc('year', current_date) + interval '1 year' - interval '1 day',
        interval '1 day'
    )::date as date_day
)

select
    date_day                                            as date_key,
    extract(year  from date_day)::int                   as year_number,
    extract(month from date_day)::int                   as month_number,
    extract(day   from date_day)::int                   as day_of_month,
    extract(quarter from date_day)::int                 as quarter_number,
    date_trunc('month', date_day)::date                 as month_start,
    to_char(date_day, 'YYYY-MM')                        as year_month,
    case extract(month from date_day)
        when 1 then 'Janeiro'   when 2 then 'Fevereiro' when 3  then 'Março'
        when 4 then 'Abril'     when 5 then 'Maio'      when 6  then 'Junho'
        when 7 then 'Julho'     when 8 then 'Agosto'    when 9  then 'Setembro'
        when 10 then 'Outubro'  when 11 then 'Novembro' else 'Dezembro'
    end                                                 as month_name,
    -- No Planalto Central a estação seca (maio a setembro) domina o clima.
    case
        when extract(month from date_day) between 5 and 9 then 'SECA'
        else 'CHUVOSA'
    end                                                 as season,
    (date_day <= current_date)                          as is_past
from days
