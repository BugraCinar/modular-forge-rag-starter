# evaluation

Kind: **optional**. Package: `forge_rag.evaluation`. Default: **on**.

Offline retrieval and citation regression suite.

## Contract and ownership

- Port: Offline runner orchestrates shared ports.
- Configuration: `MODULE_EVALUATION_ENABLED`.
- Surface: forge-rag demo/evaluate.
- Data: Public golden.json fixtures only; in-memory SQLite.

## Disable, replace or remove

Disable removes CLI availability and avoids runner import. Remove CLI branch and package to delete. These fixtures do not benchmark a live LLM.

Follow [the modular plan](../MODULAR_PLAN.md). Keep the catalog/settings/docs aligned, preserve released migrations, and run enabled/disabled plus relevant pipeline and authorization regression tests.
