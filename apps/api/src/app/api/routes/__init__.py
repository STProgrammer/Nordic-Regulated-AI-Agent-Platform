"""Product API route modules.

Each module owns a stable API boundary (prefix, tag, router) for one product
domain. The routers are intentionally operation-free in Phase 3: real endpoints are
added only by the roadmap phase that owns each domain. This package establishes the
ownership contract so later phases extend these routers instead of inventing
competing top-level paths.
"""
