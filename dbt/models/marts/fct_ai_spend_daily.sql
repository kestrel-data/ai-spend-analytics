-- One row per day, department, tool and model. Spend nobody can be matched to
-- a department is kept under 'Unallocated', never dropped.
with azure as (
  select
    u.usage_date as date,
    coalesce(k.department, 'Unallocated') as department,
    'Azure OpenAI' as tool,
    u.deployment as model,
    sum(u.cost_usd) as cost,
    sum(u.input_tokens + u.output_tokens) as tokens,
    cast(null as int64) as active_users
  from {{ ref('stg_azure_openai_usage') }} u
  left join {{ ref('stg_api_keys') }} k using (api_key_id)
  group by 1, 2, 3, 4
),

m365_days as (
  select distinct day from {{ ref('stg_m365_copilot_usage') }}
),

-- A seat costs its monthly price spread evenly over the days of the month.
m365_seats as (
  select
    d.day as date,
    coalesce(e.department, 'Unallocated') as department,
    sum(s.monthly_cost / extract(day from last_day(d.day))) as cost
  from m365_days d
  join {{ ref('stg_m365_copilot_seats') }} s
    on s.assigned_date <= d.day and (s.removed_date is null or s.removed_date > d.day)
  left join {{ ref('stg_hr_employees') }} e on e.employee_id = s.user_id
  group by 1, 2
),

m365_active as (
  select
    u.day as date,
    coalesce(e.department, 'Unallocated') as department,
    count(distinct u.user_id) as active_users
  from {{ ref('stg_m365_copilot_usage') }} u
  left join {{ ref('stg_hr_employees') }} e on e.employee_id = u.user_id
  where u.prompts > 0
  group by 1, 2
),

m365 as (
  select
    s.date,
    s.department,
    'Microsoft 365 Copilot' as tool,
    cast(null as string) as model,
    s.cost,
    cast(null as int64) as tokens,
    coalesce(a.active_users, 0) as active_users
  from m365_seats s
  left join m365_active a using (date, department)
),

-- GitHub Copilot seats are snapshotted fresh on every load day (the vendor
-- API has no seat-history endpoint), so each day's seat cost only includes
-- seats already created by that day; a seat removed before the load ran will
-- be missing from every backfilled day, including days it was billed. See PR
-- for how many usage/seat rows land under 'Unallocated'.
github_copilot_seats as (
  select
    s.as_of as date,
    coalesce(e.department, 'Unallocated') as department,
    sum(s.monthly_cost_usd / extract(day from last_day(s.as_of))) as cost
  from {{ ref('stg_github_copilot_seats') }} s
  left join {{ ref('stg_hr_employees') }} e on e.github_login = s.login
  where s.created_at <= s.as_of
  group by 1, 2
),

github_copilot_active as (
  select
    u.day as date,
    coalesce(e.department, 'Unallocated') as department,
    count(distinct u.login) as active_users
  from {{ ref('stg_github_copilot_usage') }} u
  left join {{ ref('stg_hr_employees') }} e on e.github_login = u.login
  where u.suggestions_count > 0 or u.chat_turns > 0
  group by 1, 2
),

github_copilot as (
  select
    s.date,
    s.department,
    'GitHub Copilot' as tool,
    cast(null as string) as model,
    s.cost,
    cast(null as int64) as tokens,
    coalesce(a.active_users, 0) as active_users
  from github_copilot_seats s
  left join github_copilot_active a using (date, department)
)

select * from azure
union all
select * from m365
union all
select * from github_copilot
