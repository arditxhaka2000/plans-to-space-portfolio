-- Read-path indexes for project/document history, sheet filtering, and exterior review.
-- These are additive and preserve every existing row and model revision.
begin;
create index if not exists building_documents_project_created_idx
  on public.building_documents(project_id, created_at desc);
create index if not exists building_documents_sha256_idx
  on public.building_documents(sha256);
create index if not exists processing_runs_document_created_idx
  on public.processing_runs(document_id, created_at desc);
create index if not exists drawing_sheets_run_role_idx
  on public.drawing_sheets(run_id, role, page);
create index if not exists drawing_facts_run_kind_idx
  on public.drawing_facts(run_id, kind);
create index if not exists exterior_elevations_run_direction_idx
  on public.exterior_elevations(run_id, direction);
create index if not exists exterior_components_run_kind_page_idx
  on public.exterior_components(run_id, kind, source_page);
create index if not exists exterior_models_run_created_idx
  on public.exterior_models(run_id, created_at desc);
create index if not exists exterior_assets_sha256_idx
  on public.exterior_assets(sha256);
commit;
