# Infrastructure boundary

This directory holds stable locations for Docker assets plus future Azure infrastructure and GitHub
Actions workflows. `docker/` contains development-only images and Phase 32 production images for the
API, worker, and web app. `production-local.env.example` supports credential-free local release
validation; `production.env.template` documents the later deployment configuration without
containing a secret. Azure infrastructure as code, registry pushes, and deployment remain deferred.
