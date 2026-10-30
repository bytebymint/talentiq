# Troubleshooting

**Backend unavailable:** run `Start-TalentIQ.ps1`, or the manual two-terminal startup in README. Check `data/logs/backend-error.log`. The Windows Store `python.exe` alias may not be a real interpreter; pass the actual Python path to the installer. The bundled Codex interpreter works in this environment. If pip is absent, `python -m ensurepip --upgrade` initializes it.

**Port already in use:** an existing TalentIQ instance or another application owns 3000/8000. Stop that instance from its terminal. The launcher intentionally does not kill unknown processes.

**Ollama offline:** open the Ollama application or run `ollama serve`. Verify `http://127.0.0.1:11434/api/tags`. Check the loopback URL in AI settings. AI Workspace distinguishes unreachable runtime from installed model tags. CLI detection is best-effort; a service can be reachable even if the CLI is not on PATH.

**Model tag not found:** the requested tags depend on Ollama's registry. Explicitly select/download an available local instruct model with structured-output support and update the recruitment profile's model too. TalentIQ does not silently fall back to another model or a cloud model. Embedding models cannot answer chat requests.

**Invalid model output / timeout:** try a smaller local instruct model, longer timeout, or a context length supported by your hardware. AI output gets at most two schema-validation attempts per passage. Failed candidates remain retryable. A larger context increases RAM requirements. One heavy operation runs at a time.

**Paused or stopped analysis:** use Resume / retry failed in AI Workspace. Completed checkpoints are retained. A new job skips evaluations already saved for the current profile version. Re-evaluate one candidate explicitly from Human review if needed. Changing the profile marks previous results as older-rubric evaluations.

**Image-only PDFs:** TalentIQ currently needs selectable text. Run OCR with an external local tool and reimport the searchable PDF. Never upload sensitive resumes to an online OCR service unless independently authorized. Password-protected and corrupted files show individual import errors.

**Directory picker unavailable:** Choose folder uses the browser's directory upload capability. Current Chromium browsers support it. Use multi-file selection or a ZIP as a fallback. Recursive importing is optional. No arbitrary filesystem folder is read without the browser selection.

**Semantic search unavailable:** install the chosen embedding model. Keyword fallback is labeled in search results. Re-evaluate a candidate to retry its embedding index. Changing embedding models excludes older vectors from semantic retrieval.

**AI busy:** chat, analysis, setup, and model downloads share a single heavy-operation lock. Pause the active analysis or wait for it to finish. Shutdown cancels application-owned work and requests unloading of models it loaded; it never kills the Ollama server.

**Sign-in expired:** sessions expire after 12 hours. Sign in again. Clearing browser storage does not erase server records. Restore deliberately invalidates all sessions; use a password from the restored backup. There is no default password or cloud recovery.

**Restore rejected:** use a TalentIQ-generated ZIP, not an arbitrary database export. Paths, document hashes, SQLite integrity/references, required tables, and schema version are checked. Preserve your pre-restore backup. Restores larger than the browser limit need an offline administrator migration procedure.

**PDF report characters missing:** the current report renderer uses standard PDF fonts. English/Latin reports work; full non-Latin font coverage is not yet bundled. Use Excel/CSV for multilingual names until PDF font coverage is extended.

**Tests:** pytest always uses a temporary database, not `data/`. Browser QA has its own isolated data directory and labels synthetic candidates. No test should require real resumes or a production AI mock flag.
