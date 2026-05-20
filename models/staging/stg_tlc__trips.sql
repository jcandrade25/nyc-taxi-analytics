with source as (

    select * from {{ source('tlc', 'yellow_trips_raw') }}

),

renamed as (

    select
        cast("VendorID"                as integer)        as vendor_id,
        cast(tpep_pickup_datetime      as timestamp)      as pickup_datetime,
        cast(tpep_dropoff_datetime     as timestamp)      as dropoff_datetime,
        cast(passenger_count           as integer)        as passenger_count,
        cast(trip_distance             as decimal(10, 2)) as trip_distance_miles,
        cast("RatecodeID"              as integer)        as rate_code_id,
        cast(store_and_fwd_flag        as varchar)        as store_and_fwd_flag,
        cast("PULocationID"            as integer)        as pickup_location_id,
        cast("DOLocationID"            as integer)        as dropoff_location_id,
        cast(payment_type              as integer)        as payment_type,
        cast(fare_amount               as decimal(10, 2)) as fare_amount_usd,
        cast(extra                     as decimal(10, 2)) as extra_usd,
        cast(mta_tax                   as decimal(10, 2)) as mta_tax_usd,
        cast(tip_amount                as decimal(10, 2)) as tip_amount_usd,
        cast(tolls_amount              as decimal(10, 2)) as tolls_amount_usd,
        cast(improvement_surcharge     as decimal(10, 2)) as improvement_surcharge_usd,
        cast(total_amount              as decimal(10, 2)) as total_amount_usd,
        cast(congestion_surcharge      as decimal(10, 2)) as congestion_surcharge_usd,
        cast("Airport_fee"             as decimal(10, 2)) as airport_fee_usd,
        cast(cbd_congestion_fee        as decimal(10, 2)) as cbd_congestion_fee_usd,
        cast(filename                  as varchar)        as source_filename

    from source

)

select * from renamed
