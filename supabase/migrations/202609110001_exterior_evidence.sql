-- Server-only persistence. No browser/client access policies are granted.
begin;
create table if not exists public.building_projects (id text primary key, name text not null, created_at timestamptz not null default now());
create table if not exists public.building_documents (id text primary key, project_id text not null references public.building_projects(id), sha256 text not null, filename text not null, created_at timestamptz not null default now());
create table if not exists public.processing_runs (id text primary key, document_id text not null references public.building_documents(id), status text not null, pipeline_version text not null, summary jsonb not null default '{}', created_at timestamptz not null default now());
create table if not exists public.drawing_sheets (run_id text not null references public.processing_runs(id), page integer not null check(page>0), code text, title text, role text, full_text text not null, metadata jsonb not null, primary key(run_id,page));
create table if not exists public.drawing_observation_chunks (run_id text not null, page integer not null, chunk integer not null, encoding text not null default 'gzip+json', observation_count integer not null, data bytea not null, primary key(run_id,page,chunk), foreign key(run_id,page) references public.drawing_sheets(run_id,page));
create table if not exists public.drawing_tables (run_id text not null, page integer not null, item integer not null, payload jsonb not null, primary key(run_id,page,item), foreign key(run_id,page) references public.drawing_sheets(run_id,page));
create table if not exists public.drawing_facts (run_id text not null references public.processing_runs(id), item integer not null, kind text not null, payload jsonb not null, primary key(run_id,item));
create table if not exists public.drawing_references (run_id text not null references public.processing_runs(id), item integer not null, payload jsonb not null, primary key(run_id,item));
create table if not exists public.drawing_coverage (run_id text not null, page integer not null, payload jsonb not null, primary key(run_id,page), foreign key(run_id,page) references public.drawing_sheets(run_id,page));
create table if not exists public.exterior_elevations (run_id text not null, page integer not null, direction text, payload jsonb not null, primary key(run_id,page), foreign key(run_id,page) references public.drawing_sheets(run_id,page));
create table if not exists public.exterior_components (run_id text not null references public.processing_runs(id), id text not null, kind text not null, source_page integer not null, geometry jsonb not null, verification text not null default 'unverified', primary key(run_id,id), foreign key(run_id,source_page) references public.drawing_sheets(run_id,page));
create table if not exists public.exterior_materials (run_id text not null references public.processing_runs(id), item integer not null, payload jsonb not null, primary key(run_id,item));
create table if not exists public.validation_issues (run_id text not null references public.processing_runs(id), item integer not null, payload jsonb not null, primary key(run_id,item));
do $$ declare t text; begin
  foreach t in array array['building_projects','building_documents','processing_runs','drawing_sheets','drawing_observation_chunks','drawing_tables','drawing_facts','drawing_references','drawing_coverage','exterior_elevations','exterior_components','exterior_materials','validation_issues'] loop
    execute format('alter table public.%I enable row level security',t);
    execute format('revoke all on public.%I from anon, authenticated',t);
  end loop;
end $$;
commit;
