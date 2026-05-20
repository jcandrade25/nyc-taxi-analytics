with trips as (

    select * from {{ ref('stg_tlc__trips') }}

),

cleansed as (

    select
        *,
        case
            when trip_distance_miles < {{ var('min_trip_distance_miles') }}
              or trip_distance_miles > {{ var('max_trip_distance_miles') }}
                then true
            when fare_amount_usd < {{ var('min_fare_amount_usd') }}
              or fare_amount_usd > {{ var('max_fare_amount_usd') }}
                then true
            when passenger_count is not null
              and (passenger_count < {{ var('min_passenger_count') }}
                or passenger_count > {{ var('max_passenger_count') }})
                then true
            else false
        end as is_suspect_row

    from trips
    where
        pickup_datetime  >= '2026-01-01'::timestamp
        and pickup_datetime  < '2026-04-01'::timestamp
        and dropoff_datetime >= '2026-01-01'::timestamp
        and dropoff_datetime < '2026-04-01'::timestamp
        and trip_distance_miles >= 0
        and fare_amount_usd >= -10
        and pickup_datetime < dropoff_datetime

)

select * from cleansed
