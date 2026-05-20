with trips as (

    select * from {{ ref('fct_trips') }}

)

select
    payment_type,
    payment_type_label,

    count(*)                                                as trip_count,
    cast(sum(total_amount_usd) as decimal(18, 2))           as total_revenue_usd,
    cast(avg(fare_amount_usd)  as decimal(10, 2))           as avg_fare_usd,
    cast(avg(tip_amount_usd)   as decimal(10, 2))           as avg_tip_usd,
    cast(avg(tip_pct_of_fare)  as decimal(10, 2))           as avg_tip_pct,
    cast(avg(trip_distance_miles) as decimal(10, 2))         as avg_trip_distance_miles,
    cast(avg(trip_duration_minutes) as decimal(10, 2))       as avg_trip_duration_minutes,
    sum(case when is_airport_trip then 1 else 0 end)         as airport_trip_count

from trips
group by 1, 2
