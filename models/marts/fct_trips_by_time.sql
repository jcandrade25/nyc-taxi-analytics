with trips as (

    select * from {{ ref('fct_trips') }}

)

select
    cast(pickup_datetime as date)       as pickup_date,
    extract(hour from pickup_datetime)  as pickup_hour,
    extract(week from pickup_datetime)  as iso_week,
    dayname(cast(pickup_datetime as date)) as day_of_week,
    case
        when extract(dow from pickup_datetime) in (0, 6) then true
        else false
    end as is_weekend,

    count(*)                                              as trip_count,
    cast(sum(fare_amount_usd)  as decimal(18, 2))         as total_fare_usd,
    cast(sum(total_amount_usd) as decimal(18, 2))         as total_revenue_usd,
    cast(avg(trip_distance_miles) as decimal(10, 2))       as avg_trip_distance_miles,
    cast(avg(trip_duration_minutes) as decimal(10, 2))     as avg_trip_duration_minutes

from trips
group by 1, 2, 3, 4, 5
