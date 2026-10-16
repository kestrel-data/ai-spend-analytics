-- Fails if a row has no cost value in either the legacy cost_usd column or
-- the cost column the vendor introduced on 2026-10-15. Catches a future
-- vendor change that drops cost entirely, which coalesce() alone would not.
select usage_date, api_key_id, deployment
from {{ source('raw', 'azure_openai_usage') }}
where cost_usd is null and cost is null
