# security

Kind: **required**. Package: `forge_rag.security`. Default: **on**.

Backend delegation and HTTP boundaries.

## Contract and ownership

- Port: Shared Principal and scope dependencies.
- Configuration: `DELEGATION_KEYS, DELEGATION_AUDIENCE, ALLOWED_HOSTS`.
- Surface: All protected routes; HTTP boundaries.
- Data: No owned tables.

## Disable, replace or remove

Required; replace only with a verifier preserving backend identity, audience, lifetime and scope checks.

Follow [the modular plan](../MODULAR_PLAN.md). Keep the catalog/settings/docs aligned, preserve released migrations, and run enabled/disabled plus relevant pipeline and authorization regression tests.
