# Spring Boot backend integration

Optional gateway package for the Java 21 / Spring Boot 4.1.1
[Modular Forge backend](https://github.com/BugraCinar/modular-forge-spring-boot-starter).
Source code is compiled and tested independently in this repository.

Copy `src/main/java/dev/modularforge/rag/` into the backend under the same package,
or build with `./mvnw clean verify` and add the resulting jar as a Maven module.
The sibling backend already supplies the Web MVC, security and JJWT dependencies.
Ensure `spring-boot-restclient` is present (declared in this integration's pom).
Because the package is inside `dev.modularforge`, normal component scanning finds
it. Add these properties to the backend's `application.properties`:

```properties
app.modules.rag.enabled=${MODULE_RAG_ENABLED:false}
app.rag.url=${RAG_URL:http://127.0.0.1:8090}
app.rag.issuer=forge-spring
app.rag.audience=modular-forge-rag
app.rag.delegation-key=${RAG_DELEGATION_KEY:}
app.rag.timeout=90s
```

Set `MODULE_RAG_ENABLED=true` and supply only the `forge-spring` key from the RAG
service's `DELEGATION_KEYS`, through the backend's private secret configuration.
Use HTTPS or an encrypted service mesh for cross-machine transport. This key is
separate from the backend's user access-token key.

The existing `JwtAuthFilter` checks the account's current state/authVersion,
sets the `Authentication` details to its immutable Long ID, and supplies
`ROLE_USER`/`ROLE_ADMIN`. The resolver consumes that verified context, separates
user/admin IDs, and creates `personal:forge-spring:user:<id>` (or `admin:<id>).
The existing security chain authenticates `/api/v1/rag/**` via `anyRequest()`;
do not add a permit-all matcher. The default resolver also rejects anonymous or
ambiguous accounts. If adapting to another security filter, replace the resolver
with a bean implementing `RagIdentityResolver` using verified account/membership
records. Never accept tenant/group values from request JSON.

Clients keep using their normal backend bearer token. Routes and JSON match the
[HTTP contract](../../docs/API.md), under `/api/v1/rag` instead of `/v1`.
`POST /documents` preserves 202, needs an `Idempotency-Key`, and is followed by
job polling; source deletion uses `DELETE /documents/{uuid}`. UUID paths prevent
arbitrary upstream routing. Read/write delegation scopes are minted per operation.
Apply per-user rate and spend limits in the existing backend/gateway.

For shared organization knowledge, provide a server-side identity resolver,
canonical tenant mapping, groups and document ACLs. A user ID in Python and an ID
in Java are different identities until you explicitly map them.

`MODULE_RAG_ENABLED=false` removes every bean and route without requiring a key.
To remove physically, delete `dev.modularforge.rag`, the properties, and optional
Maven dependency. No account fields or business database migrations are added.
Register the toggle in the backend module catalog when you incorporate it.
