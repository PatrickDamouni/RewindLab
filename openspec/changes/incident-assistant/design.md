# Design: read-only incident assistant

## Boundary

The core engine produces a versioned JSON evidence bundle with an integrity
digest. Local validation consumes a copy of that bundle; the optional live model
receives a selected read-only analyst view derived from it. Analysis receives
no database write handle and exposes no mutation operation. The report is
stored separately from the dataset, so even a wrong diagnosis cannot change
query results.

The offline path renders a deterministic template from the bundle, clearly
labeled as a baseline preview rather than AI output. The optional live path
invokes Hermes Agent and routes model requests through OmniRoute. Before coding
the adapter, verify the actual CLI/API and tool-permission controls in the
checked-out Hermes and OmniRoute revisions; do not assume an endpoint, provider
name, or tool-call format from memory. The live path uses environment variables
for credentials and documents the variables in `.env.example` without values.

## Report contract

The report includes run ID, case ID, fault hypothesis, event IDs supporting
that hypothesis, expected and observed results, confidence or uncertainty,
and a validation section comparing category and citations to the oracle.
The observed mismatch is `null` when the run matches the oracle.
Unsupported citations are flagged; oracle mismatch is reported, not hidden.
Prompt and model metadata may be saved for reproducibility but must not include
tokens or secrets.

## Failure handling

If the model times out, errors, or returns malformed output, preserve the
evidence bundle, emit a clear error, and leave the dataset untouched. The user
can rerun offline analysis without network access. No model output triggers an
automatic replay, correction, or remediation.
