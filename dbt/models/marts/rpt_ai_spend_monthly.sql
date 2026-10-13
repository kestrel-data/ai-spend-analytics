-- Budgets are set per department, so budget and variance are department
-- figures repeated on each tool row: sum cost across tools, never budget.
-- Costs keep full precision so totals across departments add up to the cent.
with spend as (
  select date_trunc(date, month) as month, department, tool, sum(cost) as cost
  from {{ ref('fct_ai_spend_daily') }}
  group by 1, 2, 3
),

department_spend as (
  select month, department, sum(cost) as cost
  from spend
  group by 1, 2
)

select
  s.month,
  s.department,
  s.tool,
  s.cost,
  b.budget,
  b.budget - d.cost as variance
from spend s
join department_spend d using (month, department)
left join {{ ref('stg_ai_budgets') }} b using (month, department)
