# telemetry

Kind: **optional**. Package: `forge_rag.telemetry`. Default: **on**.

Request metadata without source content.

## Contract and ownership

- Port: ASGI middleware.
- Configuration: `MODULE_TELEMETRY_ENABLED`.
- Surface: Request metadata logging.
- Data: No persisted application data.

## Disable, replace or remove

Disable removes middleware import/installation. Remove branch and package. Never add prompt/source/token logging; add exporter adapters with metadata-only events.

Follow [the modular plan](../MODULAR_PLAN.md). Keep the catalog/settings/docs aligned, preserve released migrations, and run enabled/disabled plus relevant pipeline and authorization regression tests.
