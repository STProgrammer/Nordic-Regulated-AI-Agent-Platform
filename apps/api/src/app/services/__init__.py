"""Internal application services.

Services compose repositories, validate internal commands, and translate expected
persistence failures.  They are deliberately not HTTP handlers or public API
schemas; Phase 6 and later route modules will adapt them at the API boundary.
"""
