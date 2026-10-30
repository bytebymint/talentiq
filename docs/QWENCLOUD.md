# Local AI and QwenCloud

Choose in **AI Workspace** or **Settings → AI Engine**. Provider selection is administrator-controlled; reviewers/viewers see the active provider. A new workspace asks for a provider before enabling AI.

## Behavior

| Mode | Generation and analysis | Semantic search/indexing | Local AI startup |
| --- | --- | --- | --- |
| Local AI | Profile/workspace Ollama models | Local embedding model | Starts installed runtime when explicitly selected; models load on demand |
| QwenCloud | `qwen3.8-flash`, full-CV analysis | Hosted `text-embedding-v4`, 1024 dimensions | No Ollama probes, startup, model loading or local fallback |

Local model/depth choices stay saved in each profile. Cloud analysis uses the configured cloud model with the full-CV pipeline and records its actual provider/model plus the rubric snapshot. Switching providers marks incompatible results stale. A checkpoint belonging to another provider/model cannot silently resume through the new provider.

Switching away from Local unloads models owned by TalentIQ. Shared models and unrelated applications are preserved. Cloud mode itself makes no Ollama calls. It never installs models or requires a local model server. The app's backend, original-document storage and SQLite still run on the application host.

Cloud task requests contain the selected CV text, job rubric, question and relevant chat context. The chooser explicitly discloses processing by QwenCloud in Singapore. Original documents are retained by TalentIQ; this integration sends text and embeddings requests, not entire file uploads. Local-mode CV processing remains on the host. Full-CV ownership, source checking and human-review boundaries apply to both modes.

## Credentials

The configured HTTPS endpoint is:

`https://ap-southeast-1.maas.qwencloudapi.com/compatible-mode/v1`

The supplied key was saved in the backend credential store. On Windows it is encrypted with DPAPI for the server account. On other hosts the optional saved credential file has owner-only permissions. It is outside the settings database and normal workspace backup archives; GET/settings/status responses never return a key. The browser password input clears after saving. Request headers, raw provider errors and raw reasoning traces are never displayed as answers.

For hosting, set `DASHSCOPE_API_KEY` (or `QWENCLOUD_API_KEY`) in the server's environment and `TALENTIQ_AI_PROVIDER=qwencloud` before first startup. Never expose the key through `NEXT_PUBLIC_` variables. Existing saved provider choices override the environment default. Windows-encrypted credentials cannot be copied to a different host/user; use that host's environment key. A cloud deployment needs Node/Python and application storage, without Ollama/model weights. Public deployment, HTTPS/reverse-proxy configuration and origin access rules are separate from provider selection.

## API operation

The adapter uses QwenCloud's OpenAI-compatible Chat Completions streaming and Embeddings endpoints with the existing HTTPX dependency. Generation defaults to thinking enabled with a 2,048-token thinking budget and 8,192-token combined completion limit. It exposes final answers only. Structured analysis uses JSON mode plus the exact response contract; application schema, source ownership and original-text checks determine which rows can be accepted. Context/output limits and premature stream closure raise explicit errors. No retry silently switches to Local AI.

Status polling reads configuration and the last verified connection state, without paid inference calls. **Test QwenCloud connection** sends a generic short request. AI tasks use the account's normal API quota/billing. Authentication, rate-limit, network and timeout failures have sanitized messages; local inference is never used as an error fallback. Semantic retrieval can use the existing keyword fallback if a remote query-embedding request fails, which runs no language model.

## Verification on 28 October 2026

- Supplied-key connectivity and a tiny structured comparison passed; actual response time 3.282 seconds.
- A real one-page synthetic-CV pipeline passed in an isolated temporary database: full-CV assessment/save plus hosted vector indexing **6.718 s**, streamed cited chat **4.594 s**, hosted semantic query/retrieval and connection check.
- During that run, the local Ollama client was replaced with a fail-fast guard. It was never called. All inference/embedding responses came from the actual QwenCloud API.
- A real browser selector round trip loaded the model in Local mode, then switched to QwenCloud, unloaded the owned model and retained the saved key.
- Synthetic unit contracts cover provider switching, unconfigured startup, cloud-only execution, source/model provenance, secret-safe settings/backups, interrupted streams, output caps and sanitized provider errors. Browser checks exercise the first-choice UI, disclosure, write-only key and removal of local controls in cloud mode.

These are small synthetic fixtures, not throughput promises for arbitrary real CVs. Production test CVs were not submitted by the acceptance script and were not replaced by fixtures. Results are recorded under ignored `test-results/live-cloud-results.json`.

Protocol references: [QwenCloud latest model](https://docs.qwencloud.com/developer-guides/getting-started/latest-model), [regional API keys](https://docs.qwencloud.com/api-reference/preparation/api-key), [thinking controls](https://docs.qwencloud.com/developer-guides/text-generation/thinking), [Chat Completions parameters](https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions).
