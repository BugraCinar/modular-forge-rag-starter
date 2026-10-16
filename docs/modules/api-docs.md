# api-docs

Kind: **optional**. Package: `forge_rag.app`. Default: **on**.

Development OpenAPI documentation.

## Contract and ownership

- Port: FastAPI schema/docs configuration.
- Configuration: `MODULE_API_DOCS_ENABLED`.
- Surface: /docs and /openapi.json.
- Data: No tables.

## Disable, replace or remove

Off removes both endpoints. Production requires off. Remove docs branches if unwanted; do not remove authenticated /v1/modules.

Follow [the modular plan](../MODULAR_PLAN.md). Keep the catalog/settings/docs aligned, preserve released migrations, and run enabled/disabled plus relevant pipeline and authorization regression tests.
