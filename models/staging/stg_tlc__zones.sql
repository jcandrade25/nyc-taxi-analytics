with source as (

    select * from {{ source('ref_data', 'taxi_zone_lookup') }}

),

renamed as (

    select
        cast("LocationID"   as integer) as location_id,
        cast("Borough"      as varchar) as borough,
        cast("Zone"         as varchar) as zone_name,
        cast(service_zone   as varchar) as service_zone

    from source

)

select * from renamed
