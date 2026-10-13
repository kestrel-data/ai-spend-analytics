select
  user_id,
  assigned_date,
  removed_date,
  cast(monthly_cost as numeric) as monthly_cost
from {{ source('raw', 'm365_copilot_seats') }}
