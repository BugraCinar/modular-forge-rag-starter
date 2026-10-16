# Evaluation and regression coverage

Run the bundled offline regression from the repository root after creating the
private local environment:

```sh
uv run --frozen --all-extras forge-rag evaluate
```

The runner uses public `evaluation/golden.json` fixtures, an in-memory SQLite
index, hash vectors and extractive generation. It makes no paid model calls and
does not populate the running service's database. `MODULE_EVALUATION_ENABLED`
must be enabled for the CLI command. Tests also exercise the runner directly.

| Metric | What the fixture measures |
|---|---|
| `recall_at_3` | Fraction of answerable cases with the expected document in the first three retrieved chunks. |
| `mrr_at_3` | Mean reciprocal rank of the first chunk from the expected document. |
| `citation_validity` | Answerable cases have statements whose IDs exist in the returned citations. |
| `fixture_answer_match` | The returned answer contains a case's expected literal substring. |
| `unanswerable_abstention` | The unanswerable fixture returns `insufficient_evidence`. |

The current small fixture requires each metric to equal 1; a regression causes a
nonzero command exit. These checks detect changes in the deterministic pipeline,
not the quality of a live semantic model. Citation validity does not prove that
the cited passage supports every claim, and literal matching is not entailment.

## Add a domain-specific evaluation

Keep a separate dataset of representative questions, relevant source IDs and
expected supported facts. Include unanswerable questions, near-duplicate sources,
different languages, updated/deleted documents and unauthorized tenant/ACL cases.
Keep evaluation data synthetic or privately governed; do not commit customer text.

Measure retrieval recall/rank separately from answer support, factual correctness,
abstention and prompt-injection resistance. Record the embedding/generator model,
pipeline signature, prompts, dataset version, latency and provider-reported tokens
so comparisons are interpretable. Split tuning and held-out cases, and compare
against a fixed baseline before changing chunking, thresholds or reranking.

Live evaluations should be explicit opt-in work with configured credentials,
request limits and a budget. Keep them out of the default test/CI path. For the
existing authorization and lifecycle regressions, run `tests/test_pipeline.py`,
`tests/test_jobs.py`, `tests/test_security.py` and the PostgreSQL contract test.
