-- Tip rate by (day_of_week, hour_of_day) over the OBSERVED-tip population.
-- Consumes is_cash_tip_unobservable: `not is_cash_tip_unobservable` keeps
-- credit-card (1) and app-hailed Flex Fare (0), where tips are digitally
-- captured. The credit-card-only slice is carried alongside so the dashboard
-- can toggle between "all observed tips" and "credit card only" without a
-- second mart. See the caveat__cash_tip_invisibility doc block.
with observed_trips as (

    select * from {{ ref('fct_trips') }}
    where not is_cash_tip_unobservable

)

select
    dayname(cast(pickup_datetime as date))   as day_of_week,
    extract(dow from pickup_datetime)        as day_of_week_num,
    extract(hour from pickup_datetime)       as hour_of_day,

    -- all observed tips: credit card (1) + app-hailed Flex Fare (0)
    count(*)                                              as trip_count,
    cast(avg(tip_pct_of_fare) as decimal(10, 2))          as avg_tip_pct,
    cast(avg(tip_amount_usd)  as decimal(10, 2))          as avg_tip_usd,
    cast(avg(fare_amount_usd) as decimal(10, 2))          as avg_fare_usd,

    -- credit-card-only slice (payment_type = 1) for the dashboard toggle.
    -- CASE (not FILTER) for Snowflake portability.
    count(case when payment_type = 1 then 1 end)                                    as cc_trip_count,
    cast(avg(case when payment_type = 1 then tip_pct_of_fare end) as decimal(10, 2)) as cc_avg_tip_pct

from observed_trips
group by 1, 2, 3
