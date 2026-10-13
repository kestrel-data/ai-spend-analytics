select
  department,
  month,
  cast(budget as numeric) as budget
from {{ source('raw', 'ai_budgets') }}
