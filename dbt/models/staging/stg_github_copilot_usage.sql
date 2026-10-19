{#
  New source: raw.github_copilot_usage only exists once nightly.yml has run
  the merged ingest code on main and created it. Until then (e.g. in this
  PR's ci.yml build, which runs against real raw data) the relation is
  absent, so we return the same shape with zero rows instead of failing.
#}
{% set rel = adapter.get_relation(
    database=source('raw', 'github_copilot_usage').database,
    schema=source('raw', 'github_copilot_usage').schema,
    identifier=source('raw', 'github_copilot_usage').identifier) %}

{% if rel is none %}

select
  cast(null as date) as day,
  cast(null as string) as login,
  cast(null as string) as editor,
  cast(null as int64) as suggestions_count,
  cast(null as int64) as acceptances_count,
  cast(null as int64) as lines_accepted,
  cast(null as int64) as chat_turns
where false

{% else %}

select
  day,
  login,
  editor,
  suggestions_count,
  acceptances_count,
  lines_accepted,
  chat_turns
from {{ source('raw', 'github_copilot_usage') }}

{% endif %}
