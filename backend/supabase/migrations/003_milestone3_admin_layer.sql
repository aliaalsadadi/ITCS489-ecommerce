-- Milestone 3 admin layer foundation

alter table public.profiles
  add column if not exists is_suspended boolean not null default false;

create table if not exists public.admin_action_logs (
  id uuid primary key default gen_random_uuid(),
  admin_id uuid references public.profiles(id) on delete set null,

  action text not null,
  target_type text not null,
  target_id text not null,
  details jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now()
);

create index if not exists idx_admin_logs_created_at on public.admin_action_logs(created_at desc);
create index if not exists idx_admin_logs_admin_id on public.admin_action_logs(admin_id);
create index if not exists idx_admin_logs_target on public.admin_action_logs(target_type, target_id);

alter table public.admin_action_logs enable row level security;

drop policy if exists "admin_action_logs_authenticated_all" on public.admin_action_logs;
create policy "admin_action_logs_authenticated_all" on public.admin_action_logs for all to authenticated using (true) with check (true);
