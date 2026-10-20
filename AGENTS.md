# Repository guidance

Read [docs/model-workflow.md](docs/model-workflow.md) before changing model import, PDF processing or review UI.

Current milestone: Admin creates building → uploads PDF → automatic local drawing interpretation → durable background generation → saved selectable GLB revision → review, notes and dimension correction. Recipe import is advanced optional functionality. The user's latest request supersedes the previous manual-recipe-only milestone. IQ Buildings' authored example must never be used as an automatic recognition shortcut. No generative model or paid AI integration is used.

Preserve stored project data, immutable source/model bytes and review history. Use additive schema changes. Keep PDF context extraction distinct from drawing interpretation in worker/pdf_interpret.py and geometry compilation in worker/recipe_generate.py. Recipe input is data only: never execute uploaded Python, attached scripts or arbitrary commands. Never select geometry by document name/hash. Update the JSON schema and generator/interpreter version when changing the contract/output. Do not require ordinary users to enter coordinates. Keep estimates, inferred facade correspondence and unresolved geometry visible. Unsupported drawings retain GLB/recipe fallback. Do not claim broad architectural understanding or completeness. Generated recipe lineage establishes supplied component IDs for explicit historical remaps; source notes stay on their original revisions and require recheck.

The working tree can contain unrelated work. Inspect it before editing and do not reset it. Verify model changes using the actual UMD PDF/GLB when locally available; report missing fixtures rather than inventing results.
