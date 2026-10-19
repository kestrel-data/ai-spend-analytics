select
  day,
  user_id,
  app,
  prompts,
  _load_id,
  _loaded_at
from {{ source('raw', 'm365_copilot_usage') }}
