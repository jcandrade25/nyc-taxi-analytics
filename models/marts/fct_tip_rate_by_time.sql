with credit_card_trips as (

    select * from {{ ref('fct_trips') }}
    where payment_type = 1

)

select
    dayname(cast(pickup_datetime as date))   as day_of_week,
    extract(dow from pickup_datetime)        as day_of_week_num,
    extract(hour from pickup_datetime)       as hour_of_day,

    count(*)                                              as trip_count,
    cast(avg(tip_pct_of_fare) as decimal(10, 2))          as avg_tip_pct,
    cast(avg(tip_amount_usd)  as decimal(10, 2))          as avg_tip_usd,
    cast(avg(fare_amount_usd) as decimal(10, 2))          as avg_fare_usd

from credit_card_trips
group by 1, 2, 3
