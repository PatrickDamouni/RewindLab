# Incident analysis: evidence first

RewindLab's SQLite replay and Python oracle determine correctness. The analyst
reads a **copy** of one synthetic corpus case and cannot update the data or
oracle. All six injected conditions currently pass their oracle checks, so
`injected_fault_category` describes the test condition while
`observed_mismatch` is `null`. Do not present an injected condition as a found
engine defect.

## Deterministic offline report

From the RewindLab directory:

```bash
PYTHONPATH=src python3 -m rewindlab evidence --case malformed_schema --report work/incident-evidence.json
PYTHONPATH=src python3 integrations/review_incident.py work/incident-evidence.json --report work/incident-report.json
```

The second command prints and saves a JSON report labeled `offline_template`
and `model_called: false`. It requires no network, account, or API key. The
bundle includes the exact case, seed, expected/observed results, immutable
revision and delivery evidence IDs, an `attempted:1` ID for the invalid input,
and a SHA-256 integrity digest. The digest detects edits to the bundle; it is
not a cryptographic signature. The validator also regenerates this deterministic
synthetic case and rejects a self-rehashed fabricated bundle. Each `--report`
path must be a new `.json` file; existing files and symlink paths are refused.
Choose a fresh filename when rerunning these commands. Reports cite evidence IDs,
list their supporting event IDs (including invalid attempted rows), and validate their
existence, required oracle citations, and proposed category. Free-text claims
are **not** semantically verified. To inspect the eventual model prompt:

```bash
PYTHONPATH=src python3 integrations/review_incident.py work/incident-evidence.json --print-prompt
```

`rewindlab evidence --case` accepts `baseline`, `duplicate`, `out_of_order`,
`malformed_schema`, `late_correction`, and `interrupted_import`. Omitting
`--report` writes JSON to stdout, which can be piped into the offline reviewer.
Live mode requires a saved bundle path so a provider error cannot discard the
only copy of the evidence.

## Optional Hermes Agent → OmniRoute live report

The checked-out Hermes commit is `3eb7ed08`; OmniRoute is `02f2f00e`. Their
local documentation confirms `hermes chat --query-file - --oneshot -Q`, the
custom provider settings in [hermes-config.yaml.example](hermes-config.yaml.example),
the explicit empty CLI toolset, and OmniRoute's local `/v1/models` endpoint.
The live prompt sends only an analyst view: it omits the oracle fault label,
oracle citation list, and case-name label. Its run ID is opaque so category
agreement is not answered by the prompt itself. The full saved bundle remains
available to the validator. The live adapter captures the Hermes answer, requires one strict JSON object,
validates the same evidence IDs and oracle category, and saves a separate
report only after validation. A category disagreement is recorded in the
report; malformed output, timeout, or provider failure saves no report.

1. Start OmniRoute from the checked-out source or its documented installer.
   Its dashboard is `http://localhost:20128` and API base is
   `http://localhost:20128/v1`.
2. In **Dashboard → Providers**, connect a provider that permits the use and
   has an eligible model. Copy a local OmniRoute key from **Endpoints**.
   `auto` needs an eligible route; a fresh install does not guarantee one.
3. Install the Hermes CLI from its checked-out repository or documented
   installer. The source clone alone does not put `hermes` on `PATH`.
4. Set the key in your shell and run:

```bash
export OMNIROUTE_API_KEY='paste-local-key-here'
PYTHONPATH=src python3 integrations/review_incident.py work/incident-evidence.json --live --report work/live-incident-report.json
```

Set `HERMES_BIN` to the executable path if needed. Do not put credentials in
the repository or send them in chat. The child process receives only the
OmniRoute key and essential system environment variables; it uses a fresh
temporary `HERMES_HOME`, a custom localhost endpoint, and zero CLI tools.
The selected synthetic bundle is sent to the upstream model chosen by
OmniRoute. A `/v1/models` check confirms the local API/key before Hermes runs.
The canned-mock transport smoke proves the chat route in that test setup; a
real-provider/model smoke test is still required.

The [local transport smoke](../docs/transport-smoke/README.md) ran the unchanged
adapter through Hermes and OmniRoute against a loopback mock that returned a
canned proposal. It verified transport and JSON parsing; **no language model
performed inference or diagnosed an incident**. No real upstream provider has
been tested. The adapter requests OmniRoute model `auto`, which can choose
different upstream models between runs. Category agreement rates and a fixed
upstream model remain unmeasured until a real provider is connected and six
labeled live reports are evaluated with route metadata. The offline path and
mocked live failures are tested with:

```bash
PYTHONPATH=src python3 -m unittest discover -s integrations -p 'test_*.py' -v
```

## Source checks

- Hermes: `website/docs/reference/cli-commands.md` (`--query-file`, `--oneshot`, `-Q`), `website/docs/integrations/providers.md` (custom provider), `hermes_cli/tools_config.py` (explicit empty toolset).
- OmniRoute: `README.md` (localhost endpoint, `auto`, dashboard key, and `/v1/models`).
