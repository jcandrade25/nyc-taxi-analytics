with cleansed as (

    select
        *,
        {{ dbt_utils.generate_surrogate_key([
            'vendor_id',
            'pickup_datetime',
            'dropoff_datetime',
            'pickup_location_id',
            'dropoff_location_id'
        ]) }} as trip_surrogate_id

    from {{ ref('int_trips__cleansed') }}

),

ranked as (

    select
        *,
        row_number() over (
            partition by trip_surrogate_id
            order by source_filename desc, pickup_datetime asc
        ) as rn

    from cleansed

)

select
    trip_surrogate_id,
    vendor_id,
    pickup_datetime,
    dropoff_datetime,
    passenger_count,
    trip_distance_miles,
    rate_code_id,
    store_and_fwd_flag,
    pickup_location_id,
    dropoff_location_id,
    payment_type,
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
    source_filename,
    is_suspect_row

from ranked
where rn = 1
