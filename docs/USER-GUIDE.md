# TalentIQ

**Intelligence Behind Every Hire.** A browser-based recruitment workspace backed by a local Python service, SQLite database, original resume storage, and your choice of Local AI (Ollama) or QwenCloud. There are no remote fonts or production sample candidates.


The home screen guides HR through defining a role, adding CVs and reviewing evidence. Balanced/QwenCloud reviews create a source-linked CV brief and check it in a second model pass. The recruitment copilot includes ready-written questions and default HR instructions, and checks its draft against the original CV before publishing an answer. [HR workflow and guidance](HR-WORKFLOW.md).

The language button switches the interface between English and Persian, including RTL layouts, locally bundled Persian typography, prepared HR prompts and AI response language. It remembers the choice and keeps source documents intact. [Persian language behavior and checks](PERSIAN.md).

## Install and start on Windows

Requires Node.js **22+** (24 recommended for the full toolchain) and Python **3.11–3.13**. Dependencies are installed once with internet access. From this folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\Install-TalentIQ.ps1 -IncludeAI
powershell -ExecutionPolicy Bypass -File .\Start-TalentIQ.ps1
```

If Python is not discovered, pass `-PythonPath 'C:\path\to\python.exe'` to the installer. The installer can also discover the bundled Codex Python runtime on this machine. `-IncludeAI` explicitly installs Ollama if missing and downloads the full-CV understanding, Fast, detailed review, and embedding models. Omit that flag for dependency/build setup only. `Setup-LocalAI.ps1` can also be run separately; completed model downloads are reused.

For normal use, double-click **TalentIQ.cmd**. It opens an existing healthy instance or starts the app, starts the installed Ollama runtime only when Local AI is selected, and opens the browser. In Local mode the backend warms the selected installed language model and verifies residency. Cloud startup skips all local-runtime initialization. Heavy inference is serialized. Ordinary startup never downloads model weights.

Open **http://127.0.0.1:3000** and create your local administrator account. There is no default password. Keep your password and protected backups safe; cloud password recovery is not provided. Keep the launcher terminal open. Ctrl+C stops the processes it started, without killing Ollama or unrelated applications. Interrupted analysis is recovered as paused at the next startup.

Change your own username or password in **Settings → Account**. Enter your current password, enter the new details and select **Save sign-in details**. A new password needs at least 12 characters and a matching confirmation. Successful changes rotate your current session and sign out other sessions; your workspace and AI connection are preserved.

Development alternative (two terminals):

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
npm run dev
```

`Start-TalentIQ.ps1 -Development` starts the development frontend. Production starts the built Next.js server. Both bind to loopback. Stop the existing instance before launching another. API documentation is served at http://127.0.0.1:8000/api/docs; protected operations require an authenticated browser session and `X-TalentIQ-Request: 1` on mutations.

## Choose Local AI or QwenCloud

Open **AI Workspace** and choose a provider before using AI. **Local AI** starts the installed Ollama runtime and loads local models as needed. **Third-party API · QwenCloud** sends AI task content to the configured Singapore endpoint and never starts/loads local AI or falls back to Ollama. The app, SQLite and original-file storage still run on your application host.

QwenCloud defaults to `qwen3.8-flash`, with thinking enabled and a bounded thinking-token budget. Analysis reads complete ordinary CVs; semantic search uses hosted `text-embedding-v4`. Existing profile model/depth choices apply to Local mode; cloud evaluations record the actual cloud model, provider and rubric snapshot. Older results become stale when the active provider/model changes, and checkpoints cannot silently resume through another provider.

Enter the supplied provider key in AI Workspace or Settings → AI Engine. The API accepts it only as a write-only value; it never returns the key to the browser or stores it in the workspace database. On Windows the credential store uses DPAPI bound to the server account. On other hosts a saved key uses an owner-only server file. Credentials are excluded from normal workspace backup archives. For hosting, prefer server environment variables:

```text
TALENTIQ_AI_PROVIDER=qwencloud
DASHSCOPE_API_KEY=your-server-side-key
```

Never use a `NEXT_PUBLIC_` variable for the key. The configured endpoint is `https://ap-southeast-1.maas.qwencloudapi.com/compatible-mode/v1`; keys are region-specific. No Ollama installation or model download is needed in cloud mode. On a fresh installation no provider is selected and local AI is not started. Existing workspace selections override the environment default.

Cloud status polling does not make paid inference requests. **Test QwenCloud connection** sends a tiny generic test; analysis, chat and semantic indexing make the actual API calls. The UI discloses the remote processing boundary. Provider/network/quota errors are shown; no raw reasoning traces or credentials are exposed. See [QwenCloud setup and verification](QWENCLOUD.md).

## CV understanding and analysis

New profiles default to **Balanced** with `qwen3.5:4b-q4_K_M`. It reads every ordinary CV page and cites numbered original passages; the application binds source quotations to their document/page and applies rubric weights. Larger documents split into checkpointed parts. CPU inference can take several minutes. **Fast** with `qwen3:0.6b` remains available as a quick evidence screen. Standard/Detailed support the original review model. [Full-CV pipeline](CV-UNDERSTANDING.md) · [Historical Fast measurements](FAST-PIPELINE.md).

The copilot reads selected CV pages directly, with candidate ownership attached to every source. Comparisons send the selected candidate IDs. It does not use a handful of global semantic matches as the answer context, and similarity values are never presented to the chat model as qualification scores. Source coverage, model and elapsed time are visible; long-document excerpts are labeled. Prior answers from the old pipeline are preserved for reference but excluded as factual context.

## Local models

Install [Ollama](https://ollama.com/download), open it (or run `ollama serve`), and explicitly download:

```powershell
ollama pull qwen3.5:4b-q4_K_M
ollama pull qwen3:0.6b
ollama pull qwen3:4b-instruct
ollama pull qwen3-embedding:0.6b
```

The full-CV default is qwen3.5:4b-q4_K_M; qwen3:0.6b is optional Fast screening. The original detailed-review and embedding tags remain supported. Model tag availability depends on the Ollama library; if a requested tag is unavailable, choose an available **local instruct model with structured-output support** in AI settings and in the recruitment profile. The application never silently substitutes a model within a saved profile version. AI Workspace shows actual tags, running models, runtime version, and download progress, and can request a download with administrator confirmation. The authorized setup on this machine installed Ollama 0.40.12 and the requested local models on 28 October 2026.

The requested tags are available in the official library: [qwen3:4b-instruct](https://ollama.com/library/qwen3%3A4b-instruct) and [qwen3-embedding:0.6b](https://ollama.com/library/qwen3-embedding%3A0.6b). Use the synthetic regression tests below before running real inference with your own documents.

In Settings → AI Engine, select the language and embedding models, timeout, context limit, temperature, and memory duration. Each profile separately pins its evaluation model. Start AI warms the workspace model and verifies its residency through `/api/ps`. The backend uses Ollama's [documented local API](https://github.com/ollama/ollama/blob/main/docs/api.md), including structured chat outputs, embeddings, model listing, pull progress, and `keep_alive: 0` unload requests.

In Local mode, once dependencies and models are installed, normal operation requires no internet. Install Ollama with local-only inference enabled; TalentIQ rejects cloud model tags and accepts HTTP loopback endpoints only. Local mode sends no CV content to an external service. Cloud mode sends AI task content to the explicitly selected QwenCloud endpoint. Official installation links are opened only when explicitly selected.

## Workflow

1. **Recruitment Profiles:** build a five-step role profile. Add mandatory/preferred requirements and weighted criteria. Enabled weights must total exactly 100%. Export/import JSON or duplicate a profile to reuse a rubric. AI-proposed criteria require explicit approval before they are applied to the draft. Saving an edit creates a new immutable version.
2. **Recruitment Projects:** assign the profile to a hiring project. Use the header selector to establish project context. Projects can be edited and archived.
3. **Import resumes:** select multiple PDF/DOCX files, a computer folder, or a ZIP. Directory selection is browser-authorized. Subfolder import is optional; the structure becomes internal folders. Each original file has a 25 MB limit. Import in as many batches as needed; there is no 50-document project limit. The API allows up to 250 files per request and applies archive size and expansion limits.
4. **Resume Folders:** create nested folders, preview originals or extracted text, download originals, rename display names, and bulk-move references. SHA-256 duplicates within a project are reported and not imported again. Matching display names are flagged for manual verification and never automatically merged. Copy a candidate reference into another project from Human review; its evaluations and reviews remain independent.
5. **AI Workspace:** start an analysis for the selected project. One heavy operation runs at a time. Each document is chunked; structured outputs are validated. Every scored claim must contain a passage found at the stated source location. Results are saved progressively, with the exact profile snapshot, model, scoring version, duration, and source references.
6. **Review:** sort/filter rankings and select top N or all candidates. Inspect evidence, original resumes, skills, questions, and unknown requirements. Human shortlist flags are separate from AI scores. Record reviewer notes, ownership, interview dates, and pipeline status. Hired/Not Selected require explicit human confirmation plus a rationale note. Remove a candidate through the confirmed deletion action in Human review.
7. **Compare:** select 2–6 candidates within a project, inspect criteria and sources side by side, save sessions, discuss them with the local copilot, and export a PDF.
8. **Talent Search & Copilot:** semantic retrieval uses indexed local embeddings; clearly labeled keyword retrieval is the fallback when indexing is unavailable. Chat streams locally, supports Stop generation, persists personal conversation history within the project, cites retrieved sources, and cannot perform workflow changes. Always inspect sources; model-generated answers can still be wrong.
9. **Reports:** export rankings, human shortlist, individual evaluations, comparisons, project summaries, and activity as PDF, Excel, or CSV. PDF detailed reports include source passages and explanations. Spreadsheet exports contain compact result/provenance rows. Original contact details and protected administrative data are excluded.

## How scores work

Scoring versions `documented-v1` and `documented-fast-v1` calculate `sum(criterion_score × weight / 100)` outside the model. Criterion scores are model interpretations of source-supported job evidence; exact quote validation is necessary but does not independently authenticate a CV or guarantee the model's interpretation.

An unknown criterion has a null criterion score and earns no **documented points**. It stays **Not established**, never a claim that the person lacks the qualification. All-unknown evaluations have a null overall score. Evidence coverage is the weight of criteria with validated evidence; it is **not statistical confidence**. Conflicting chunk assessments are withheld for human review. Chunk merging uses the highest supported score for a criterion; holistic cross-chunk interpretation is a known limitation. The ranking order is points descending, coverage descending, import time, then stable candidate ID. Scores do not represent a person's worth, future performance, or an automatic hiring recommendation.

The model receives an unweighted rubric, with exact criterion IDs constrained by the response schema. Application code attaches document/page references to compact responses and validates every source passage. Supported rows require quotations. If a small model swaps a quotation into its explanation field, that text is accepted only when it is itself an exact source substring. Stable instructions/schema precede resume text to improve local prompt-cache reuse. Standard output is capped at 1,024 tokens; detailed output at 2,048. Default timeout is 20 minutes for CPU workloads and remains configurable. The original 4B CPU workload generated roughly 2–3 tokens/second. Fast mode uses a smaller model and shorter output; see the measured limits linked above. Long profiles and CPU throttling can still make inference take minutes.

Protected traits are excluded from rubric fields, scoring evidence, supported facts, and ordinary search. Common explicit sensitive-data lines are redacted before inference. The system prompt treats CVs and profile text as untrusted and prohibits demographic assessment. These layers reduce risk; they are not a proof of fairness or immunity to prompt injection. Do not use this application for autonomous hiring decisions. Optional sensitive administrative fields are deliberately **not collected in this release**.

## Pause, stop, recovery, and shutdown

Pause/Stop immediately acknowledge the request, cancel the application's current async inference request, stop scheduling additional candidates, and retain completed evaluation checkpoints. A candidate interrupted before its evaluation commit stays pending. Resume retries pending/failed work without repeating completed evaluations. A new analysis skips evaluations already completed against the current profile version. Re-evaluate from the candidate detail to explicitly run another evaluation.

**Ollama does not expose a reliable per-client execution-termination acknowledgement.** A closed HTTP request is not proof that internal model computation has ended. TalentIQ reports this limitation instead of claiming model execution has definitively stopped. Shutdown closes owned requests, requests unloading through supported APIs, and checks residency. Models already resident when TalentIQ encountered them are preserved. Ollama has no per-client model ownership leases, so shared runtime ownership cannot be guaranteed; use a dedicated local Ollama instance for recruitment workloads. The application never kills Ollama processes.

On backend restart, interrupted job states become paused and active candidate checkpoints return to pending. Completed evaluations and their profile versions remain persisted. Run **only one backend worker**; job orchestration is deliberately single-process.

## Data, access, and backups

- SQLite runs with WAL, foreign keys, and a numbered schema migration ledger. Entity models live in `backend/db.py`; startup applies additive migration v1 and job recovery. Future destructive schema changes need explicit migration code.
- Default storage: `data/talentiq.db` and `data/documents/`. Original content uses hashed storage paths. `.env.example` documents the supported storage and initial Ollama environment variables; the launcher reads only those allowed variables.
- Sessions use random tokens stored as hashes, HTTP-only SameSite Strict cookies, 12-hour expiry, and PBKDF2-SHA256 password hashes. State changes require a same-origin request header; origin and host validation reject remote browser origins and hosts. Default HTTP is suitable for loopback, not a company network.
- Admins manage users, AI settings, retention, backup, and restore. Reviewers manage recruitment workflows. Viewers have read-only access. All accounts share one authorized workspace; per-project membership ACLs are not implemented. Retrieval, comparisons, reports, and candidate selections enforce their project context.
- Settings → Privacy & Security provides full ZIP backup, verified backup restore, and a retention review/deletion action. Restore validates paths, document hashes, schema version, database integrity, and references, then clears sessions. It replaces records and retains any unreferenced physical blobs; perform a fresh backup first. Browser restore has a 512 MB upload / 2 GB expanded limit. Backups are unencrypted and include resumes and password hashes; protect them with OS access controls/encryption.
- Candidate deletion removes associated evaluations, embeddings, notes, and its document references. Original file blobs are retained only when another project references the same file. Audit records retain candidate IDs/action metadata, and previously downloaded backups are not retroactively erased.
- Audit events include document access, imports, settings changes, evaluations, exports, and manual reviews. The UI displays the latest 500 events; project activity exports include full retained event history. Logs omit CV content; the launcher disables backend access logging.

## Test and verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm run typecheck
npm run build
npm run test:ui
```

Python tests create a separate temporary SQLite database. They cover a 50-PDF synthetic import batch, duplicates, parsing failures, profile validation/version history, scoring, hallucinated evidence rejection, protected-field controls, deterministic ranking, role access, origin checks, project isolation, folder cycles, human final-decision confirmation, report signatures, backup/restore, crash recovery, pause/resume checkpoint preservation, and cancellation before the worker begins. Mock inference exists **only in tests**. The browser script uses an isolated temporary backend and synthetic fixtures; production starts empty. See `docs/ACCEPTANCE.md` for real-model acceptance steps and current verification results.

## Current limits

- Local model performance depends on available memory and CPU/GPU resources. The current installation uses CPU inference; no discrete inference GPU was detected. Real model runs use source-verified evidence, but their interpretations still require human review. Test results and remaining acceptance scope are recorded in `docs/ACCEPTANCE.md`.
- Automatic Tesseract OCR, DOCX visual pagination, native document editing, drag-to-move folders, advanced arbitrary folder reference copies, user invitation/email, and sensitive administrative reporting are not implemented. Use external OCR and the supported bulk-move/candidate-reuse flows.
- English and Persian interfaces are available. Evaluation explanations follow the selected language while source quotations preserve the original text. Checked CV briefs include documented employment, education, qualifications and evidence links; source validation does not independently authenticate a CV.
- Local embeddings are stored as versioned SQLite JSON vectors. Search uses a small in-process cosine scan. It is appropriate for the requested dozens-of-resumes scale, not a large enterprise corpus. Failed embedding indexing falls back to keywords; re-evaluating the candidate retries indexing. AI suggestions/chat/analysis serialize heavy work; download cancellation is through shutdown.
- The scoring/evidence guards have automated tests; model fairness, factual accuracy, and prompt-injection robustness have not been certified. Human review remains required.

For source publication, see the [GitHub checklist](GITHUB.md).

See [troubleshooting](TROUBLESHOOTING.md) for recovery instructions and [architecture](ARCHITECTURE.md) for implementation boundaries.
