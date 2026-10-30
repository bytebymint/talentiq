# Source verification

The local application supports English and Persian, original PDF/DOCX imports, folders, source-linked CV analysis, candidate comparisons, HR review notes, selected-resume deletion, backups, and username/password changes. AI can use Ollama or the configured QwenCloud API.

Run `python -m pytest -q`, `npm run typecheck`, `npm run build`, and `npm run test:ui` after installing dependencies. Python tests create a temporary database. Browser tests use synthetic documents and an isolated backend; they do not modify normal workspace records.

Mocked inference tests verify application behavior and source validation. They do not prove that every real model answer is accurate. Real inference requires the owner's own selected provider, model or API key and separate review against the original documents.

Private operational diagnostics, actual account data, uploaded CVs and generated test reports are not part of this source distribution.
