# Troubleshooting by symptom

Use request IDs and job status/error codes for diagnosis. Keep service keys,
tokens, documents and provider payloads out of shared logs or issue reports.

| Symptom | Check |
|---|---|
| Startup rejects delegation settings | Run `init-env` for a new private environment, or verify distinct random 32-byte Base64 keys in the configured issuer map. |
| `/health/ready` returns 503 | Confirm database connectivity and run the explicit `forge-rag migrate` command with the same configuration. |
| HTTP 400 before a route runs | Check the request's Host against `ALLOWED_HOSTS`; do not add wildcard hosts in production. |
| HTTP 401 on `/v1/*` | Use the backend delegation rather than a user JWT; check issuer, audience, matching backend key and synchronized clocks. |
| HTTP 403 | The verified delegation lacks the read/write scope required by that operation. |
| Job remains queued | Start the separate worker; confirm API/worker use the same database and allow any retry delay to expire. |
| Job fails with `pipeline_changed` | Align worker/API pipeline settings, then resubmit authoritative content with a new idempotency key. |
| HTTP 415 for PDF | Enable `MODULE_PDF_ENABLED` and install the PDF extra in the worker/API environment. |
| PDF job fails with `invalid_document` | Check encryption, text-layer availability, size and parser limits. Scanned pages require an OCR adapter. |
| HTTP 409 for ingestion | Reuse a key only for the identical request; use a new event/version key for changed content or ACLs. |
| HTTP 409 `context_changed` | Evidence changed during generation. Retry the question against current content. |
| HTTP 503 `corpus_capacity` | The authorized SQLite corpus exceeds its configured scan limit; use PostgreSQL for the larger corpus. |
| HTTP 503 `provider_unavailable` | Privately check the selected model, credentials, dimensions, network and timeout; do not expose raw diagnostics. |

## No answer after successful ingestion

Check that the job is completed, the requested dataset matches, and the document
belongs to the delegation's tenant and owner/subject/group ACL. An update hides
the old revision until the new one is ready. A changed pipeline signature hides
incompatible evidence until it is reindexed.

`insufficient_evidence` also occurs when retrieval admits no useful chunks or
the generator abstains. The default hash/extractive providers test the pipeline;
they do not implement semantic language understanding. Use the authenticated
search endpoint with synthetic examples to inspect admitted evidence before
changing thresholds. Threshold changes need evaluation, not a blanket reduction
to make every question return an answer.

Backend gateways sanitize upstream failures, so inspect the RAG service's
metadata/error codes privately when a gateway only reports `rag_request_failed`.
