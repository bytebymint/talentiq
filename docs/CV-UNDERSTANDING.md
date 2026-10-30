# Full-CV understanding

The default pipeline prioritizes source understanding over the old fastest screen.

## Source handling

- Original PDFs/DOCX files and their extracted pages stay in the local workspace.
- Chat resolves the candidate name or explicit comparison selection before building context. Every page includes its candidate, document and page number.
- Ordinary selected CVs are read in full on every question. Employment summaries or search similarity values do not replace the original pages.
- Long-document fallback allocates space to each selected candidate and visibly labels focused excerpts. The model must not treat an unseen detail as absent from the complete CV.
- Ambiguous singular pronouns ask for a candidate instead of silently choosing from a comparison. Follow-up questions can resolve the named candidate from the same conversation.
- Prior assistant answers from the old retrieval pipeline are retained, labeled and excluded from generation context. Current history also checks document hashes and evidence scope.
- Inline source citations open the original at the cited page. The source panel remains available even when the model fails to insert a particular inline citation.

## Models and assessment

In Local AI mode, the workspace copilot and new Balanced profiles use `qwen3.5:4b-q4_K_M`. QwenCloud mode uses its workspace cloud model for full-CV analysis and chat; local model/depth preferences stay saved separately. [Provider setup](QWENCLOUD.md). Fast with `qwen3:0.6b` remains optional. Existing profiles pin their own model, and a profile change creates an immutable new version; historical evaluations retain their old model and rubric.

Balanced supplies all ordinary CV pages plus the unweighted job rubric. It builds a structured CV brief and proposed assessment, then checks both against the original source text in a second call. The brief covers work history, demonstrated versus listed skills, projects, education, credentials, achievements, clarification points and interview questions. Brief quotations must match the original text; work-history fields must appear in the supporting quotes. First-pass proposals checkpoint independently from checked results. The model cites numbered passages rather than inventing quote strings. The application binds these IDs to original quotations, validates the document/page text, applies weights and saves the result. Unknown and invalid rows remain unknown. Long CV parts checkpoint before the next part; semantic indexing happens after evaluations save. A model's interpretation of a real passage still requires HR review—quote existence alone does not establish semantic correctness or authenticate an employer/credential.

Local inference disables extra thinking and uses six CPU threads, a 12,288-token default context and bounded output. QwenCloud uses the cloud context and thinking preference. One heavy operation stays active. Chat holds its draft privately, checks it in a second call against the original selected CVs, and only then publishes a corrected answer with a source-check marker. Failed checks leave no unchecked assistant answer saved. Checked briefs help navigate the sources; original pages remain authoritative. Both passes use the same model, so HR review remains necessary.

## Verification

`tests/test_memory.py` covers candidate identity, actual dates, complete page coverage, partial coverage, project isolation, scoped history, legacy-answer exclusion and original evidence binding. The browser suite separately checks selected comparison IDs, Markdown tables, inline page links and model/coverage labels.

Run `python -m pytest tests/test_understanding.py tests/test_memory.py -q` for synthetic CV-reading and source-isolation regression tests. Inspect real model answers against original evidence separately.

CPU timings depend on CV length, rubric size, output length and other work on the machine. One minute per CV and perfect comprehension are not guarantees. OCR, unusual layouts and long comparisons can require more time or manual clarification. See `ACCEPTANCE.md` for actual measured runs.
