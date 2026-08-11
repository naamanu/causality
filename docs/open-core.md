# Open-core repository model

`naamanu/causality` is the MIT-licensed public product and source of truth for the
core data model, OTLP ingestion, investigations, analysis pipeline, local stack,
and stable extension contract. Fixes to shared behavior land here first.

GitHub does not support private branches in a public repository. Proprietary code
therefore belongs in a separate private repository, `causality-enterprise`, owned
by the team organization. Do not push paid source, customer configuration, license
keys, production secrets, or unreleased commercial plans to this repository on
any branch.

## Boundary

The public backend loads no extension by default. A proprietary Python package may
expose `create_extension()` and be selected with `CAUSALITY_EXTENSION_MODULE`.
The returned extension can contribute FastAPI routers and startup validation while
the public application retains authentication, tenancy, telemetry, and analysis.

Good candidates for the private layer include commercial entitlements, advanced
organization policy, enterprise audit exports, premium connectors, and managed
deployment integration. Security fixes, protocol compatibility, core reliability,
and generally useful telemetry behavior stay public.

The private repository should:

1. depend on a pinned Causality commit or release;
2. publish the enterprise package/image only to private GitHub Packages/GHCR;
3. call this repository's reusable `.github/workflows/ci.yml` for core checks;
4. run its own contract and end-to-end tests against the pinned public core;
5. keep customer and deployment secrets in GitHub environments, never in source.

Do not use a git submodule as an access-control boundary. Prefer a versioned private
package and a private image build so public/core and paid releases are reproducible.
