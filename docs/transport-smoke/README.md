# Local Hermes → OmniRoute transport smoke

Tested on 2026-10-10 UTC against Hermes Agent `3eb7ed08d19da393196722d0b219b2ba1ec22810` and OmniRoute `02f2f00e7654ae19b9f930728c4e1bd22a4870d7`.

**Scope:** This was a transport and JSON-contract check with a Python standard-library mock. The mock returned fixed text or a canned incident proposal. No language model performed inference or diagnosed an incident. The temporary servers were stopped after the test.

## Setup and route

- Installed OmniRoute's locked source dependencies with `npm ci --no-audit --no-fund` and Hermes's pinned local runtime with `bash ./setup-hermes.sh --runtime-only --test-environment`. `HOME`, caches, runtime, `TMPDIR`, and OmniRoute `DATA_DIR` were placed inside an isolated workspace directory.
- Started OmniRoute with `HOST=127.0.0.1 PORT=20128 OMNIROUTE_E2E_BOOTSTRAP_MODE=open REQUIRE_API_KEY=false npm run dev`. The `open` setting is a test-only fixture. A temporary local API key was created for the actual client calls; its value is absent from this record.
- Started a loopback-only OpenAI-compatible mock on `127.0.0.1:20129`. It implemented `GET /v1/models` and `POST /v1/chat/completions`, accepted both streamed and regular responses, and recorded request bodies without authorization headers.
- Created an OmniRoute `openai-compatible` chat node with prefix `rewindmock`, base URL `http://127.0.0.1:20129/v1`, a credential-free connection, and model `rewindlab-smoke-1`. `/v1/models` advertised `rewindmock/rewindlab-smoke-1`. OmniRoute's dev `sync-models` route failed with Next `spawn EBADF`, so this local fixture added the model through `POST /api/provider-models`.

## Checks

| Check | Observed result |
| --- | --- |
| OmniRoute → mock | `POST /v1/chat/completions` returned `REWINDLAB_TRANSPORT_OK_5D21`; mock captured upstream model `rewindlab-smoke-1`. |
| Hermes → OmniRoute → mock | `hermes chat --query-file - --oneshot --format stream-json --ignore-rules` exited 0. Its `system`, `text`, and `result` events carried the route model and marker. The mock captured a matching chat request. |
| OmniRoute `auto` route | A direct chat request for model `auto` returned the same marker through the mock. |
| Unchanged RewindLab live adapter | Generated the `malformed_schema` evidence bundle, then ran `python3 integrations/review_incident.py <bundle> --live --report <new-report>`. Its actual `hermes chat --query-file - --oneshot -Q` call, `model.default: auto`, and strict JSON parser produced a report with `mode: live_hermes_omniroute`, `fault_category: schema_rejection`, and a passing oracle citation check. The mock captured the analyst-view prompt and run ID. |

The canned proposal cited `attempted:1`, `run:import-error`, `run:expected`, and `run:observed`. The report's `model_called: true` means the adapter made an HTTP model API call; the responding endpoint was a mock. The proposal came from RewindLab's deterministic offline template, which knew the injected fault. It is **not evidence of model diagnostic accuracy**.

The source-only Hermes runtime needed a temporary `HERMES_BIN` launcher because the adapter passes a restricted child environment and the source setup used `--runtime-only`, which does not publish a global `hermes` executable. The adapter's fresh Hermes home also incurred a sizable first-run cache/install on this machine. Real-provider behavior and six-case live accuracy remain unmeasured.

After pruning disposable download and per-run caches, the ignored local install still occupies about **3.8 GB for OmniRoute dependencies** and **1.7 GB for the isolated Hermes runtime**. Those directories are local setup state and are not part of this documentation artifact.

See [smoke-result.json](smoke-result.json) for a sanitized machine-readable summary. No API key, account token, temporary filesystem path, or raw prompt is in either record.
