# Hermes Agent + OmniRoute incident reviews

RewindLab's replay and point-in-time query results are computed by RewindLab. This integration gives Hermes Agent a **read-only JSON snapshot** to summarize for a human engineer. The default command is offline and does not require an account, API key, or running service.

## Offline review packet

From the RewindLab directory, pipe the core demo's actual JSON report into the reviewer:

```bash
PYTHONPATH=src python3 -m rewindlab demo --json | python3 integrations/review_incident.py -
```

This prints the exact prompt that would be sent to Hermes. It makes no network request and does not change either cloned repository. You can also pass a JSON file path. The report must be a JSON object (maximum 128 KB). The core demo data is synthetic.

## Optional live review

1. Start OmniRoute. The cloned source supports `npm install` followed by `npm run dev` from `../OmniRoute`, or use its documented installation method. The local dashboard is `http://localhost:20128`; the API base URL is `http://localhost:20128/v1`.
2. In **Dashboard → Providers**, connect an eligible upstream provider that permits your intended use. Then copy an OmniRoute API key from **Dashboard → Endpoints**. OmniRoute alone does not supply a guaranteed usable model; `auto` needs at least one eligible route.
3. Install the Hermes CLI using its documented installer or prepare the cloned source as described in the Hermes repository. The clone is source code, not an installed command.
4. Set the OmniRoute key in your shell session, then run a live review:

```bash
export OMNIROUTE_API_KEY='paste-key-here'
PYTHONPATH=src python3 -m rewindlab demo --json | python3 integrations/review_incident.py - --live
```

If your Hermes executable is not on `PATH`, set `HERMES_BIN` to its absolute path. Do not put the key in RewindLab files or commit it.
The repository's [`.env.example`](../.env.example) lists the optional variable names without credentials.

Live mode first checks OmniRoute's `/v1/models` endpoint. It then starts `hermes chat --query-file - --oneshot -Q` with [hermes-config.yaml.example](hermes-config.yaml.example) in a fresh temporary `HERMES_HOME`. The config selects the custom endpoint, model `auto`, and `OMNIROUTE_API_KEY` as a credential pointer. Hermes resolves the explicit empty CLI toolset to zero tools in the checked-out source. The subprocess receives only the OmniRoute key and essential system variables; other provider credentials and Hermes config overrides are omitted. The temporary home is removed after the command exits. The snapshot is transmitted to the upstream model chosen by OmniRoute; only use synthetic or otherwise approved data.

`/v1/models` proves that the local API and key work; the subsequent chat call is the actual route check. Upstream provider usage or charges depend on the connected account. Hermes output is an analysis aid and must not modify the deterministic dataset or serve as evidence that replay is correct.

Live mode has not been verified in the initial checkout because no upstream OmniRoute provider or Hermes CLI is configured. The offline packet and its error paths are covered by `python3 -m unittest discover -s integrations -p 'test_*.py' -v`.

## Repository evidence used

- Hermes: `website/docs/integrations/providers.md`, **Custom & Self-Hosted LLM Providers**; `website/docs/reference/cli-commands.md`, `hermes chat`; `hermes_cli/tools_config.py`, empty platform toolset resolution.
- OmniRoute: `README.md`, **Quick Start**, for local URL, API key location, `auto`, and `/v1/models`.
