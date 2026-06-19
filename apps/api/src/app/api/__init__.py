"""HTTP API boundary: shared schemas, dependencies, middleware, and routing.

This package owns the public API surface. The product route modules under
``app.api.routes`` are stable ownership boundaries; their operations are added by
the roadmap phase that owns each domain, not here.
"""
