select
  day,
  user_id,
  app,
  prompts
from {{ source('raw', 'm365_copilot_usage') }}
