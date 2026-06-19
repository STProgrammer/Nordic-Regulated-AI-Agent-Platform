"""Core, reusable API infrastructure (configuration, logging, errors).

These modules hold cross-cutting concerns that route handlers depend on but must
not re-implement. They are intentionally free of persistence, authentication, and
business logic, which arrive in later roadmap phases.
"""
