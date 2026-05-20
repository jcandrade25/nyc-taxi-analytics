-- Trips should not have negative total revenue unless they are
-- refunds/disputes (payment_type = 3 or 4) or voided trips (payment_type = 6).
-- Configured as warn because a small number of negative-amount adjustments
-- are normal in TLC data (meter corrections, partial refunds).
-- {{ config(severity='warn') }}

select
    trip_surrogate_id,
    payment_type,
    fare_amount_usd,
    tip_amount_usd,
    tolls_amount_usd,
    total_amount_usd

from {{ ref('fct_trips') }}

where
    total_amount_usd < 0
    and payment_type not in (3, 4, 6)
