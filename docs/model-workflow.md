# Model workflow

This portfolio copy contains the reusable application and processing code. Original drawings, extracted image sets, authored building recipes and historical project evidence are excluded.

## Processing

An administrator creates a building and uploads a PDF. The API stores the original privately and queues durable jobs. PDF context extraction produces searchable text and page previews; drawing interpretation is a separate operation. The interpreter reads supported scale, plan, height and elevation evidence, then produces a validated internal building recipe. The deterministic compiler creates a selectable GLB and saves a model revision.

Jobs deduplicate by document and processing version. Failed or unsupported inputs retain diagnostics. Interrupted running jobs are requeued. No filename or document hash selects an example building or model. No LLM or paid generative service is required.

## Review

The viewer places source pages beside the 3D model. Reviewers select components, create groups, change visibility and add source-linked notes. Supported dimensional corrections create a new revision. Original document/model bytes and previous notes stay attached to their source revisions. Identity across imported revisions requires explicit remapping rather than matching names alone.

## Access and storage

ASP.NET Core provides cookie authentication, building-scoped authorization, CSRF protection and upload/rate limits. SQLite stores application records and job state. Source PDFs, model bytes, recipes and reports live in private artifact storage. Source commits do not supply a populated production database.

## Limits

Automatic interpretation is limited to supported drawing structures. Complex boundaries, raster ambiguity, missing heights and conflicting dimensions may require input or prevent generation. Reports retain estimates and inferred placements. A draft is not a certified architectural reconstruction, structural assessment or takeoff.

## Run

Follow the root README for dependencies, client build and the local PowerShell launcher. First-time setup asks for the administrator password locally. The service listens at http://127.0.0.1:5088.

## Verify

Build the .NET service and TypeScript client, then run the synthetic colour and PDF interpretation checks described in the README. Create local work/ and evidence/ directories before running scripts that write output.

Some integration scripts still describe the private development fixtures and are retained as implementation references. They are not part of a self-contained public test suite. In particular, recipe/model-import checks need separately supplied PDFs, GLBs and authored recipes. The public copy makes no historical benchmark claim.
