with source as (

    select * from {{ ref('rate_codes') }}

),

typed as (

    select
        cast(rate_code_id    as integer) as rate_code_id,
        cast(rate_code_label as varchar) as rate_code_label

    from source

)

select * from typed
