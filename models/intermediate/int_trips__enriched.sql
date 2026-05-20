with trips as (

    select * from {{ ref('int_trips__deduped') }}

),

zones as (

    select * from {{ ref('stg_tlc__zones') }}

),

payment_types as (

    select * from {{ ref('stg_tlc__payment_types') }}

),

rate_codes as (

    select * from {{ ref('stg_tlc__rate_codes') }}

),

enriched as (

    select
        t.trip_surrogate_id,
        t.vendor_id,
        t.pickup_datetime,
        t.dropoff_datetime,
        t.passenger_count,
        t.trip_distance_miles,
        t.rate_code_id,
        rc.rate_code_label,
        t.store_and_fwd_flag,
        t.pickup_location_id,
        puz.borough       as pickup_borough,
        puz.zone_name     as pickup_zone_name,
        puz.service_zone  as pickup_service_zone,
        t.dropoff_location_id,
        doz.borough       as dropoff_borough,
        doz.zone_name     as dropoff_zone_name,
        doz.service_zone  as dropoff_service_zone,
        t.payment_type,
        pt.payment_type_label,
        t.fare_amount_usd,
        t.extra_usd,
        t.mta_tax_usd,
        t.tip_amount_usd,
        t.tolls_amount_usd,
        t.improvement_surcharge_usd,
        t.total_amount_usd,
        t.congestion_surcharge_usd,
        t.airport_fee_usd,
        t.cbd_congestion_fee_usd,
        t.source_filename,
        t.is_suspect_row,

        -- derived: trip duration
        datediff('minute', t.pickup_datetime, t.dropoff_datetime)
            as trip_duration_minutes,

        -- derived: average speed
        case
            when datediff('minute', t.pickup_datetime, t.dropoff_datetime) > 0
            then round(
                t.trip_distance_miles
                / (datediff('minute', t.pickup_datetime, t.dropoff_datetime) / 60.0),
                2
            )
        end as average_speed_mph,

        -- derived: tip percentage of fare.
        -- Guard fare > 0 so zero fares (NULLIF) and negative-fare
        -- adjustments don't produce skewed/negative percentages.
        case
            when t.fare_amount_usd > 0
            then round(
                t.tip_amount_usd / nullif(t.fare_amount_usd, 0) * 100,
                2
            )
        end as tip_pct_of_fare,

        -- derived: airport trip flag
        case
            when puz.service_zone = 'Airports' or doz.service_zone = 'Airports'
            then true
            else false
        end as is_airport_trip,

        -- derived: cash-tip unobservable flag.
        -- Tip observability is a property of the payment rail, not the row.
        -- Credit card (1) and app-hailed Flex Fare (0) both capture tips
        -- digitally — INCLUDING genuine zero tips — so both are observable.
        -- Cash (2) is never metered; no-charge (3), dispute (4), unknown (5),
        -- and voided (6) are non-standard settlements where a tip is not
        -- meaningfully recorded. Those are the unobservable set.
        case
            when t.payment_type in (2, 3, 4, 5, 6) then true
            else false
        end as is_cash_tip_unobservable

    from trips as t
    left join zones as puz
        on t.pickup_location_id = puz.location_id
    left join zones as doz
        on t.dropoff_location_id = doz.location_id
    left join payment_types as pt
        on t.payment_type = pt.payment_type
    left join rate_codes as rc
        on t.rate_code_id = rc.rate_code_id

)

select * from enriched
