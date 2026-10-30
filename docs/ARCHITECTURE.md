# Architecture

Next.js 15 / React 19 / TypeScript provides the localhost UI. Locally bundled Inter, Lucide icons, semantic light/dark tokens, responsive tables, accessible dialogs, focus trapping, reduced-motion support, and a command palette form the TalentIQ design system. CSS handles restrained state transitions; no remote imagery, generated headshots, Three.js, or scroll engine is needed for a dense recruitment application.

The Next server proxies `/api/*` to FastAPI on `127.0.0.1:8000`. Authentication cookies remain same-origin. All Ollama traffic is owned by the backend. No arbitrary Ollama URL proxy is exposed.

Backend responsibilities:

| Module | Responsibility |
|---|---|
| `db.py` | SQLAlchemy entities, WAL/foreign-key setup, migration ledger, safe interrupted-job recovery |
| `schemas.py` | Strict Pydantic request and model-output validation; rubric invariants |
| `documents.py` | Signature/size/archive checks, PyMuPDF/DOCX extraction, source chunking, explicit sensitive-line redaction |
| `ai.py` | Loopback-only Ollama provider, structured output, streaming, embeddings, model diagnostics/lifecycle |
| `scoring.py` | Exact source-evidence validation, deterministic weighted points, unknown handling, stable sorting |
| `jobs.py` | Single-heavy-operation queue, per-candidate transactions, checkpoint recovery, task cancellation |
| `main.py` | Auth/roles, project-bound routes, imports, reviews, retrieval, streaming chat/SSE, analytics, reports, backup/restore |

SQLite holds structured records and embeddings; original files are immutable hashed blobs. Each evaluation stores a full profile snapshot. Each completed evaluation and its completed job item checkpoint commit in the same transaction. Resume resumes the existing job snapshot; starting a new job uses the current profile version.

SSE emits persisted job snapshots and an audit revision. Browser reconnect does not spawn another worker. An application refresh reloads database state. Live UI state never stands in for a persisted completed result.

Current security boundary is one machine and one authorized workspace. Scaling to a server requires TLS, secure cookies, project ACLs, robust rate limiting, durable external job coordination, encrypted secrets/storage, service isolation, and a formal deployment migration. Single-worker services and conservative inference are deliberate at this scale.
