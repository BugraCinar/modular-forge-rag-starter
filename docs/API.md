# HTTP contract

All `/v1/*` endpoints require `Authorization: Bearer <backend-delegation>`.
The public backend integrations expose equivalent operations at `/api/v1/rag/*`,
using the existing backend's normal user token. Health endpoints are public.
Request bodies reject unknown fields, including client-provided tenant identity.

## Documents

`POST /v1/documents` requires `rag:write` and `Idempotency-Key` (1–128 characters,
letters/digits/`_.:-`). It returns 202:

```json
{"id":"job UUID","document_id":"document UUID","revision":1,"status":"queued","attempts":0,"error_code":null}
```

Body: `external_id` (stable 1–128 character key), `title`, `content`, `dataset`
(default `default`), `media_type` (`text/plain`, `text/markdown`, `application/pdf`),
`read_subjects` (namespaced `issuer:subject`), `read_groups`. Owner read/write
rights are implicit. Subject/group ACLs grant read only, never update/delete.
ACL entries are limited to 100 each, and 200 characters each.

Documents are unique per tenant/dataset/external ID. Only their owner can update
them. A repeated idempotency key with different content/ACL/pipeline is 409.
Existing readers cannot overwrite an owner's source. Updates pause retrieval of
the previous revision. A terminal failure needs resubmission with a new key.

`GET /v1/jobs/{id}` is owner-only and requires `rag:write`. Statuses are `queued`,
`running`, `completed`, `failed`, `superseded`, `deleted`. Error codes are
`invalid_document`, `provider_unavailable`, `pipeline_changed`,
`attempts_exhausted`, `processing_failed`. Details contain no source content.

`GET /v1/documents/{id}` requires read authorization and returns metadata, state,
revision and active revision. `DELETE` requires owner/write authorization and
returns 204; it removes chunks/ACL/metadata and clears source data from jobs.
Reusing an unpurged deleted job's idempotency key returns 410.

## Retrieval

`POST /v1/search` or `/v1/query` needs `rag:read`:

```json
{"question":"What is the returns policy?","dataset":"default","top_k":5}
```

`question` is 1–2000 characters; `top_k` is 1–10. Search returns a `matches` list
with chunk IDs, document ID/revision, title, text, page and normalized-text
offsets, cosine similarity, lexical score and RRF score. Scores are heuristics.

Query returns:

```json
{
  "status":"answered",
  "answer":"Returns are accepted within 30 days.",
  "statements":[{"text":"Returns are accepted within 30 days.","chunk_ids":["chunk UUID"]}],
  "citations":[{"chunk_id":"chunk UUID","document_id":"document UUID","title":"Returns","revision":1,"page":null,"start":0,"end":35,"excerpt":"Returns are accepted within 30 days."}],
  "usage":{}
}
```

No evidence or a provider abstention returns `status=insufficient_evidence` with
empty answer/statements/citations. Unknown provider citations return 502; a
document changed/revoked during generation returns 409 and should be retried.
Usage contains provider-reported input/output/total tokens when available, not a
price estimate. Treat all source/answer text as untrusted and render it escaped.

## Errors and health

Errors use `{"error":{"code":"...","message":"..."},"request_id":"UUID"}`.
401 is missing/invalid delegation; 403 is missing scope; unauthorized resource
IDs return 404; 409 is a revision/idempotency/context conflict; 413 is size;
415 is a disabled extractor; 422 is invalid input; 503 is provider/schema/corpus
capacity failure. Backend gateway modules sanitize upstream failure details.

`GET /health/live` reports process liveness. `/health/ready` checks schema/DB,
not paid model availability. `/v1/modules` is authenticated and reports the
enabled module catalog. Development-only `/docs` and `/openapi.json` are disabled
when `MODULE_API_DOCS_ENABLED=false` (required for production mode).
