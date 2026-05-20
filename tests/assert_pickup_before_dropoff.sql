-- No time-travel trips: pickup must be strictly before dropoff.

select
    trip_surrogate_id,
    pickup_datetime,
    dropoff_datetime

from {{ ref('fct_trips') }}

where pickup_datetime >= dropoff_datetime
