# Modular plan

Composition is explicit in `runtime.py` and `app.py`. Domain services consume
contracts from `shared/ports.py`. Only the composition root chooses provider,
PDF and reranker adapters. The business backend integrations are independent
packages; neither imports the RAG implementation or adds account fields.

Read the target [module guide](modules/) before changing it. Required modules
must preserve tenant/ACL filtering, explicit migrations, grounded output and
lease-fenced publication. Replaceable modules must satisfy the same port and
negative authorization tests. Optional modules have a settings toggle and must
remove their routes/jobs/imported extras when disabled.

1. Identify the module's port, dependencies, configuration, routes and owned data.
2. Change its package; put the smallest shared contract in `shared`, not a concrete
   adapter import in a neighboring feature.
3. Update catalog, `.env.template`, guide and optional extra if applicable.
4. Verify enabled/disabled behavior, tenant/ACL regressions and relevant adapter
   contracts. Add real regression tests for behavioral changes.
5. Keep released migrations immutable. Removal of a module does not automatically
   delete retained tables or historical documents; use an explicit migration.

To remove an optional module physically, disable it first, remove its conditional
composition branch and catalog entry, then delete its package and extra. Keep
any required shared contract. For ingestion removal keep the independent
`chunking` module/signature, so query-only instances can read the existing index.
No optional feature can add fields to a business backend's account model.
