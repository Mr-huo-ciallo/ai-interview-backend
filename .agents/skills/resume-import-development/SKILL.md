---
name: resume-import-development
description: Maintain and extend this project's resume PDF extraction and job JSON import workflows. Use for parser providers, extraction schemas, import APIs, previews, tests, or diagnosing import failures.
---

# Resume Import Development

Read `docs/resume-import.md` before changing the workflow. Treat it as the operational contract and update it when limits or provider decisions change.

Keep these boundaries intact:

- `routers/career.py` owns HTTP and upload concerns.
- `services/resume_import.py` owns `ResumeParserPort`, PDF validation, extraction, and provider fallback.
- `schemas.ResumeStructuredData` is the single output schema for rules and LLM responses.
- `services/career.py` owns job import validation, deduplication, and confirmation.
- The frontend must preview imported content and require explicit confirmation before persistence.

When adding a parser provider, implement `ResumeParserPort` and preserve the existing response schema. Do not branch the router or frontend by provider. Keep PDF bytes and resume text out of logs.

Validate changes with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

If frontend behavior changes, also run `npm run build` in the sibling `ai-interview-platform` repository. Add OCR or an external PDF provider only when the evidence criteria in `docs/resume-import.md` are met.
