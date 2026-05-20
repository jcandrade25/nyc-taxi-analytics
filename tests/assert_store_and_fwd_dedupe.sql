-- Runs against int_trips__cleansed (NOT __deduped) to surface
-- surrogate-key collisions before deduplication removes them.
-- A small number of collisions is expected with store_and_fwd_flag='Y'
-- rows due to vendor timestamp jitter on retransmit.
-- Configured as warn so the build continues to __deduped which resolves them.
-- {{ config(severity='warn') }}

with keyed as (

    select
        {{ dbt_utils.generate_surrogate_key([
            'vendor_id',
            'pickup_datetime',
            'dropoff_datetime',
            'pickup_location_id',
            'dropoff_location_id'
        ]) }} as trip_surrogate_id

    from {{ ref('int_trips__cleansed') }}

),

duplicates as (

    select
        trip_surrogate_id,
        count(*) as row_count

    from keyed
    group by trip_surrogate_id
    having count(*) > 1

)

select * from duplicates
