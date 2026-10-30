# English and Persian

Use the language button in the header, sign-in screen or dialog header. The same choice is available in Settings → General. The preference belongs to the browser and survives refreshes. Switching language preserves current forms and navigation. A cookie supplies the initial server-rendered language and direction; browser storage remembers the same choice.

Persian mode uses right-to-left layouts, locally bundled Vazirmatn, Persian numerals in display text and the Persian calendar for displayed dates. Original timestamps, API values, document files, names, technical identifiers and source quotations are retained. Translated select labels still submit their canonical API values. No font CDN or translation widget is loaded.

The catalog covers navigation, forms, dialogs, validation and errors, progress states, audit metadata, accessibility labels and prepared HR instructions. HR terminology and the prepared prompts have editorial overrides. The production build includes a source-string coverage fixture; browser checks also audit rendered text for untranslated application labels. Raw CV content and user-written data are source material, not interface labels.

New copilot responses follow the chosen interface language. New analyses record their output language without rewriting the saved profile or source documents. Switching the interface alone does not invalidate existing evaluations. Existing AI explanations can be translated on demand with the selected AI provider; original evaluation data stays intact. This uses the same selected-provider disclosure and operation gate as other AI tasks. Cloud mode does not start Local AI.

Translation results are cached in bounded process/browser memory. Original names can be protected by placeholders before model generation; citation markers and numerical details must survive validation. A failed or busy translation displays a Persian retry message. It does not silently present an English explanation as a completed Persian translation. Source quotations remain verbatim and are not replaced with translations.

The website's sign-in, not-found page and local API guide also support Persian. Downloaded originals and machine-readable API identifiers remain unchanged.

Font: [Vazirmatn project](https://rastikerdar.github.io/vazirmatn/en), distributed locally through the pinned `@fontsource-variable/vazirmatn` package under its OFL license.

Checks: `python -m pytest -q`, `npm run build`, and `node scripts/test-ui.mjs`. The browser suite runs against synthetic data in an isolated temporary workspace.
