-- email and name are personal data, so they stop here.
select
  id as employee_id,
  github_login,
  department,
  plant
from {{ source('raw', 'hr_employees') }}
