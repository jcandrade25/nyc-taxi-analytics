-- Credit-card trips with zero tip are legitimate (rider chose not to tip).
-- This test flags when the zero-tip rate exceeds 15% of credit-card trips,
-- which would indicate a data-collection anomaly rather than rider behavior.
-- {{ config(severity='warn') }}

with credit_card_trips as (

    select
        count(*) as total_cc_trips,
        sum(case when tip_amount_usd = 0 then 1 else 0 end) as zero_tip_cc_trips

    from {{ ref('fct_trips') }}
    where payment_type = 1

)

select *
from credit_card_trips
where zero_tip_cc_trips > total_cc_trips * 0.15
