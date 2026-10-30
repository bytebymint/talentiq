# Publishing this source

This directory is the GitHub source distribution. Use this directory when creating the repository, rather than copying the complete development workspace.

Included: the Next.js interface, Python backend, local and QwenCloud AI integrations, English/Persian translations, synthetic tests and setup instructions.

Excluded: credentials, real CVs, account databases, environment overrides, private operational tools, generated builds, backups and logs. Review `git status` and the staged diff before the first commit; do not force-add ignored files.

Install Node.js 22 or later (24 recommended), Python 3.11–3.13, then follow the README. Run the backend tests, type check and production build before pushing. Provider credentials belong in environment variables or the application's server-side credential store, never in source files.

The owner has not selected an application license. Retain the bundled font's SIL Open Font License in `public/fonts/OFL.txt`.
