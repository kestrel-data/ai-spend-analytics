select
  usage_date,
  api_key_id,
  deployment,
  input_tokens,
  output_tokens,
  cast(coalesce(cost_usd, cost) as numeric) as cost_usd,
  _load_id,
  _loaded_at
from {{ source('raw', 'azure_openai_usage') }}
