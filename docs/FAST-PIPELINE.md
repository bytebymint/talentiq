# Local Fast mode

Fast mode uses `qwen3:0.6b`. `qwen3:4b-instruct` remains installed for Standard/Detailed review. All inference stays in the local Ollama service. Ordinary startup never downloads weights.

The application extracts page-bound passages and retrieves a representative source for each rubric item. The model returns short match labels; application code attaches the original quotation, document ID and page. The model does not copy quotations or look up source numbers. Weights are applied outside the model. Explicit minimum-year requirements can be checked against unambiguous, explicitly stated professional-experience durations; the application does not invent durations from dates.

Retrieval uses explicit term overlap and conservative education/certification anchors. Overlap alone never awards points: the model still judges the source/qualification pair. No retrieved evidence means **Not established**, not a claim that the person lacks the qualification. This can miss synonyms, equivalent learning or evidence outside the representative passage. Review unknowns and use a fuller assessment when nuance matters. Fit labels map to 25/50/75/100 points; coverage is evidence availability, not statistical confidence. Source matching does not authenticate CV claims.

One short request normally screens an ordinary CV. Up to three ambiguous source matches receive small targeted checks. The primary response is checkpointed before follow-ups, so pause/resume does not repeat the full request. Longer documents use bounded batches across all extracted pages. Fingerprints include document content, profile snapshot, model tag and pipeline version. Identical completed evaluations are reused; changed sources invalidate them.

Assessments save before semantic indexing. Index failures retain saved evaluations; Resume indexing retries missing vectors without repeating assessment. Previously indexed passages are reused. Biographies and interview questions are requested through Copilot rather than generated during every initial screen.

On this machine (Intel i7-10810U, 16 GB RAM, CPU inference), the final synthetic test used the actual six-criterion/four-requirement Senior AI Engineer rubric and a fictional two-page CV. All six criteria and four requirements were established with correctly assigned source excerpts: 86.25 documented points. The primary request took 32.484 seconds including load/prefill, and three short checks took 5.375 seconds combined. Generation measured 10.78 tokens/sec in the primary request and about 15–17 tokens/sec in the checks. The unrelated negative fixture remained unknown with no points; retrieval did not schedule inference for it. These are functional checks, not certified recruitment accuracy or a universal speed guarantee.

Several local models and protocols were compared before selecting this path. Experimental models remain installed on demand. Six CPU threads measured fastest in a short 2/4/6-thread comparison. These historical timings depend on the machine and rubric. Use the synthetic backend tests for reproducible source checks.

The active profile was upgraded through a new version. Earlier snapshots, original files, notes and evaluations remain saved. SQLite backups are in `data/backups/before-fast-activation-*.db`. Fast mode never automatically shortlists, rejects or hires anyone.

The actual three-CV project run completed in **73.507 seconds**, with per-CV times of **36.75, 14.24, and 22.41 seconds**, zero assessment/indexing failures, and persisted quotations checked against the original stored pages. Existing semantic indexes were reused. This measurement is specific to that run, not a throughput guarantee for new uploads.
