begin;
create table if not exists public.exterior_assets (
  run_id text not null,
  revision_sha256 text not null,
  asset_path text not null,
  sha256 text not null,
  mime_type text not null,
  content bytea not null,
  primary key(run_id, revision_sha256, asset_path),
  foreign key(run_id, revision_sha256) references public.exterior_models(run_id, revision_sha256)
);
alter table public.exterior_assets enable row level security;
revoke all on public.exterior_assets from anon, authenticated;
commit;
