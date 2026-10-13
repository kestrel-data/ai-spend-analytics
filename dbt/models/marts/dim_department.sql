select distinct department from {{ ref('stg_hr_employees') }}
union distinct
select 'Unallocated'
