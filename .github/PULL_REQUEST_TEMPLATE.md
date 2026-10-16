## Change

Describe the concrete problem and resulting ingestion, query or integration behavior.

## Validation

List the checks and results. For adapter changes, describe the mocked contract;
for retrieval changes, include relevant isolation and offline evaluation results.

## Compatibility

State whether clients, configuration, schema or the pipeline signature change.
Explain reindexing, retained data and retry/rollback implications if applicable.
For documentation-only changes, say so.

- [ ] Module ownership, optional toggles and removal guides are consistent.
- [ ] Tenant/ACL filtering and job fencing remain intact; relevant checks pass.
- [ ] No paid provider calls, service keys or customer documents are included in tests or diagnostics.
