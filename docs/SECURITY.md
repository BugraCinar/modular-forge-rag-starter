# Security boundaries

The service trusts only configured backend issuers. Each issuer has a distinct
32-byte random Base64 key, separate from user JWT keys. Delegations require
HS256, exact audience/issuer, `rag-delegation+jwt` header/type, identity claims,
groups/scopes and a maximum 60-second lifetime. Backend integrations resolve
identity after existing current-account checks; they never use browser tenant
or group claims. A compromised authorized backend can impersonate identities
within its trust domain. Plan key distribution and network policy accordingly.

Owner, subject and group access are enforced before vector/lexical candidate
limits. Tenant, dataset, revision and pipeline signature apply to both searches.
Readers cannot update/delete or inspect owner job payloads. Unknown/unauthorized
document IDs return 404. After generation, evidence IDs are checked again for
current access and existence. Short-lived delegations can outlive a membership
change by up to 60 seconds. No replay cache or immediate distributed revocation
service is included.

The API accepts bounded text/Markdown or opt-in PDF content, not URLs, executable
tools, Office archives or filesystem paths. PDF support reads a text layer and
rejects encrypted/no-text documents. Parser limits do not eliminate decompression
bombs; isolate workers with resource limits. Body byte limits apply even without
Content-Length. Validation and upstream errors do not echo submitted secrets.

Retrieved text is untrusted. Prompt instructions separate question/evidence from
instructions; providers have no tools. Unknown citations and incomplete outputs
are rejected. These controls do not guarantee immunity to prompt injection or
hallucination. Render answers/excerpts escaped; never execute returned text/HTML,
SQL or shell commands. Source text sent before revocation cannot be unsent.

There is no shared answer cache or stored conversation history, avoiding those
cross-tenant disclosure paths. Secrets, source text, questions and answers are
not written to runtime logs. HTTP and DB transport security, quotas, provider
retention and backup retention remain deployment responsibilities. CORS is not
opened; the RAG API is intended for backend-to-backend requests.

Report vulnerabilities privately through the maintainer's GitHub contact or
GitHub private vulnerability reporting when enabled. Do not attach credentials
or sensitive customer documents to public issues. CI dependency checks and
CodeQL are maintenance controls, not proof that a deployment is secure.
