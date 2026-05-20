with zones as (

    select * from {{ ref('stg_tlc__zones') }}

)

select
    {{ dbt_utils.generate_surrogate_key(['location_id']) }} as zone_key,
    location_id,
    borough,
    zone_name,
    service_zone

from zones
