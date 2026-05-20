with source as (

    select * from {{ ref('payment_types') }}

),

typed as (

    select
        cast(payment_type_code  as integer) as payment_type,
        cast(payment_type_label as varchar) as payment_type_label

    from source

)

select * from typed
