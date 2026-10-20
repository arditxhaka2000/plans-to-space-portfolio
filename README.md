# Plans to Space

This is a public portfolio snapshot of a privately developed project. Original architectural PDFs, extracted drawing images, authored building examples and project-specific evidence are omitted. The application code is included; private fixture-dependent checks are documented separately.

A workspace for turning building drawings into a 3D draft that can be inspected and corrected. Upload a PDF, let the background worker interpret the drawing, then review the result beside its source pages.

The interesting part is keeping the drawing evidence, model parts and review history connected. A generated draft can contain estimates or unresolved geometry, so those need to remain visible when someone reviews it.

## The workflow

1. An administrator creates a building and uploads its PDF.
2. The backend stores the original and queues background processing.
3. Python workers extract searchable PDF context and separately interpret supported drawing geometry.
4. A validated building recipe is compiled into a GLB model with selectable parts.
5. The reviewer opens the PDF and model together, selects components, adds notes and makes supported corrections as new revisions.

Unsupported drawings can use a supplied GLB or a manually prepared recipe. Closing the browser does not stop a queued job.

## Stack

| Part | Built with |
| --- | --- |
| API and background jobs | C#, ASP.NET Core / .NET 10 |
| Application data | Entity Framework Core, SQLite |
| Viewer | TypeScript, Three.js, Vite |
| Drawing processing | Python, pdfplumber, PDFium, RapidOCR |
| Geometry | OpenCV, Shapely, validated recipes and GLB generation |

## What is implemented

- Building workspaces, document upload and access control.
- PDF text extraction, page previews and OCR for searchable drawing context.
- Local drawing interpretation using scale evidence, plan boundaries, labels and repeated elevation linework.
- Durable processing jobs, deduplication and restart recovery.
- Selectable model components, grouping, visibility controls and source-linked notes.
- Model revision history, original-file preservation and explicit component remapping.
- A correction workflow that saves a new revision rather than overwriting the previous model.

Automatic interpretation uses local document and geometry processing. It does **not** require an LLM, a paid AI service or a generative model.

## Architecture

```text
Browser: PDF pages + Three.js model review
                     |
              ASP.NET Core API
              auth, workspaces, revisions
                     |
          SQLite + private artifact storage
                     |
              background job worker
                     |
       Python PDF context / interpretation
                     |
           validated recipe -> GLB
```

PDF context extraction, drawing interpretation and geometry generation are separate steps. Finding a dimension in text does not by itself establish where a wall or window belongs. Interpretation reports retain measurements, assumptions and issues alongside the model.

See [`docs/model-workflow.md`](docs/model-workflow.md) for the full workflow, routes, versioning rules and recorded verification results.

## Run locally

The supplied launcher is for Windows / PowerShell. Install .NET 10, Node.js and Python first.

From the repository root:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r worker/requirements.lock.txt
npm --prefix client install
npm --prefix client run build
./tools/start-portal.ps1 -AdminEmail 'admin@example.com'
```

On first launch, the script asks for an administrator password locally. Open `http://127.0.0.1:5088/login`. For later runs with an existing database:

```powershell
./tools/start-portal.ps1 -SkipBootstrap
```

The launcher starts a local development service. Deployment needs separate HTTPS, storage, access and process configuration.

## Verification

```powershell
dotnet build server -o work/recipe-build
npm --prefix client run build
.venv/Scripts/python.exe tools/test_pdf_colors.py
.venv/Scripts/python.exe tools/test_pdf_interpret.py
```

The repository also includes integration checks for model imports, authorization, CSRF, job processing, note persistence and revision history. Some checks need the original external PDF/GLB fixtures and will not run from a fresh checkout alone; see the workflow documentation for those requirements.

## Limits

This produces reviewable drafts, not certified architectural models or construction takeoffs. Raster drawings, complex or open boundaries and missing dimensions can prevent interpretation or require estimates. Facade correspondence and some placements are inferred. Conflicting dimensions remain unresolved until reviewed. The documented benchmarks describe specific fixtures, not accuracy across arbitrary building plans.

## Repository layout

```text
server/       ASP.NET Core API, authentication and job services
client/       TypeScript / Three.js viewer and review pages
worker/       PDF interpretation and geometry generation
tools/        Launchers, processing utilities and verification scripts
docs/         Workflow and building-recipe schema
examples/     Authored recipe examples
evidence/     Recorded checks and drawing-review notes
```
