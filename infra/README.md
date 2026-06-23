# Infrastructure boundary

This directory holds Docker assets, local production-image configuration, GitHub Actions boundaries,
and the planned Azure deployment boundary. `docker/` contains development and production images for
the API, worker, and web app. `production-local.env.example` supports credential-free local release
validation; `production.env.template` documents the platform-supplied deployment configuration
without containing a secret. Azure infrastructure as code, registry pushes, and public deployment
remain intentionally unimplemented; see [deployment readiness](../docs/deployment-readiness.md).
