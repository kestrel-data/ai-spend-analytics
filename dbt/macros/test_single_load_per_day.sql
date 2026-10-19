{% test single_load_per_day(model, column_name) %}
-- Fails if a day in this model was ever written by more than one load,
-- which is what happened when replace_day's delete-then-append was not
-- atomic (DATA-109): a second load landed before the first one's rows
-- were removed, so both stuck around.
select
  {{ column_name }} as usage_day,
  count(distinct _load_id) as load_count
from {{ model }}
group by 1
having count(distinct _load_id) > 1
{% endtest %}
