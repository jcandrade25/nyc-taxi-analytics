with date_spine as (

    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2026-01-01' as date)",
        end_date="cast('2026-04-01' as date)"
    ) }}

),

dates as (

    select
        cast(date_day as date) as date_day,
        extract(year from date_day)    as year,
        extract(month from date_day)   as month,
        extract(day from date_day)     as day_of_month,
        extract(dow from date_day)     as day_of_week_num,
        dayname(cast(date_day as date))           as day_of_week_name,
        extract(week from date_day)    as iso_week,
        case
            when extract(dow from date_day) in (0, 6) then true
            else false
        end as is_weekend

    from date_spine

)

select * from dates
