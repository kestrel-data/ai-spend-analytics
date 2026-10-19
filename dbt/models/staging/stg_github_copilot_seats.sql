{#
  Same new-source bootstrap issue as stg_github_copilot_usage: return zero
  rows in the right shape until raw.github_copilot_seats exists.
#}
{% set rel = adapter.get_relation(
    database=source('raw', 'github_copilot_seats').database,
    schema=source('raw', 'github_copilot_seats').schema,
    identifier=source('raw', 'github_copilot_seats').identifier) %}

{% if rel is none %}

select
  cast(null as string) as login,
  cast(null as string) as plan_type,
  cast(null as date) as created_at,
  cast(null as numeric) as monthly_cost_usd,
  cast(null as date) as as_of
from (select 1)
where false

{% else %}

select
  login,
  plan_type,
  created_at,
  cast(monthly_cost_usd as numeric) as monthly_cost_usd,
  as_of
from {{ source('raw', 'github_copilot_seats') }}

{% endif %}
