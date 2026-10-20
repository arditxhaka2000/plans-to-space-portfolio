begin;
create table if not exists public.exterior_models (
  run_id text not null references public.processing_runs(id),
  revision_sha256 text not null,
  status text not null,
  complete boolean not null default false,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  primary key(run_id, revision_sha256)
);
alter table public.exterior_models enable row level security;
revoke all on public.exterior_models from anon, authenticated;
commit;
