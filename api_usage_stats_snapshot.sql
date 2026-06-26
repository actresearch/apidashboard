-- API dashboard usage snapshot
--
-- Purpose:
--   Keep the dashboard from exporting every raw api_request_logs row on each page refresh.
--   The dashboard reads this small pre-aggregated table instead.
--
-- Apply this in Supabase SQL Editor or through your migration process.
-- After applying, run:
--   select public.refresh_api_usage_stats_snapshot();

create table if not exists public.api_usage_stats_snapshot (
  dimension text not null check (dimension in ('api_name', 'product_id')),
  name text not null,
  call_count bigint not null default 0,
  window_days integer not null default 30,
  window_start timestamptz not null,
  window_end timestamptz not null,
  refreshed_at timestamptz not null default now(),
  primary key (dimension, name)
);

comment on table public.api_usage_stats_snapshot is
  'Daily 30-day aggregate used by API_Dashboard /api/usage_stats to avoid raw log egress.';

alter table public.api_usage_stats_snapshot enable row level security;

revoke all on table public.api_usage_stats_snapshot from anon, authenticated;
grant select on table public.api_usage_stats_snapshot to service_role;

create index if not exists idx_api_request_logs_created_at
  on public.api_request_logs (created_at);

create or replace function public.refresh_api_usage_stats_snapshot(p_window_days integer default 30)
returns void
language plpgsql
set search_path = public
as $$
declare
  v_window_end timestamptz := now();
  v_window_start timestamptz := v_window_end - make_interval(days => p_window_days);
begin
  if p_window_days is null or p_window_days < 1 then
    raise exception 'p_window_days must be a positive integer';
  end if;

  create temp table tmp_api_usage_stats_snapshot on commit drop as
    select
      'api_name'::text as dimension,
      coalesce(nullif(api_name, ''), '(missing api_name)') as name,
      count(*)::bigint as call_count,
      p_window_days as window_days,
      v_window_start as window_start,
      v_window_end as window_end,
      v_window_end as refreshed_at
    from public.api_request_logs
    where created_at >= v_window_start
      and created_at < v_window_end
    group by 1, 2
    union all
    select
      'product_id'::text as dimension,
      coalesce(nullif(product_id, ''), '(missing product_id)') as name,
      count(*)::bigint as call_count,
      p_window_days as window_days,
      v_window_start as window_start,
      v_window_end as window_end,
      v_window_end as refreshed_at
    from public.api_request_logs
    where created_at >= v_window_start
      and created_at < v_window_end
    group by 1, 2;

  delete from public.api_usage_stats_snapshot;

  insert into public.api_usage_stats_snapshot (
    dimension,
    name,
    call_count,
    window_days,
    window_start,
    window_end,
    refreshed_at
  )
  select
    dimension,
    name,
    call_count,
    window_days,
    window_start,
    window_end,
    refreshed_at
  from tmp_api_usage_stats_snapshot;
end;
$$;

revoke all on function public.refresh_api_usage_stats_snapshot(integer) from public;

-- Optional Supabase Cron setup. Run this if pg_cron is enabled for the project.
-- It refreshes the snapshot once daily at 06:05 UTC.
--
create extension if not exists pg_cron with schema extensions;

 do $$
 begin
   if exists (
     select 1
     from cron.job
     where jobname = 'refresh-api-usage-snapshot-daily'
   ) then
     perform cron.unschedule('refresh-api-usage-snapshot-daily');
   end if;

   perform cron.schedule(
     'refresh-api-usage-snapshot-daily',
     '5 6 * * *',
     'select public.refresh_api_usage_stats_snapshot();'
   );
 end;
 $$;
