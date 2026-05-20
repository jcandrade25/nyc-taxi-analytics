with trips as (

    select * from {{ ref('fct_trips') }}

)

select
    pickup_location_id,
    pickup_borough,
    pickup_zone_name,
    pickup_service_zone,

    count(*)                                                as trip_count,
    cast(sum(total_amount_usd) as decimal(18, 2))           as total_revenue_usd,
    cast(sum(fare_amount_usd)  as decimal(18, 2))           as total_fare_usd,
    cast(avg(fare_amount_usd)  as decimal(10, 2))           as avg_fare_usd,
    cast(sum(tip_amount_usd)   as decimal(18, 2))           as total_tips_usd,
    cast(avg(total_amount_usd) as decimal(10, 2))           as avg_total_amount_usd

from trips
group by 1, 2, 3, 4
