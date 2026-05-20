with enriched as (

    select * from {{ ref('int_trips__enriched') }}
    where is_suspect_row = false

)

select
    trip_surrogate_id,
    vendor_id,
    pickup_datetime,
    dropoff_datetime,
    passenger_count,
    trip_distance_miles,
    rate_code_id,
    rate_code_label,
    store_and_fwd_flag,
    pickup_location_id,
    pickup_borough,
    pickup_zone_name,
    pickup_service_zone,
    dropoff_location_id,
    dropoff_borough,
    dropoff_zone_name,
    dropoff_service_zone,
    payment_type,
    payment_type_label,
    fare_amount_usd,
    extra_usd,
    mta_tax_usd,
    tip_amount_usd,
    tolls_amount_usd,
    improvement_surcharge_usd,
    total_amount_usd,
    congestion_surcharge_usd,
    airport_fee_usd,
    cbd_congestion_fee_usd,
    trip_duration_minutes,
    average_speed_mph,
    tip_pct_of_fare,
    is_airport_trip,
    is_cash_tip_unobservable

from enriched
