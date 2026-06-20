"""Controlled errors that may safely cross orchestration boundaries."""

from __future__ import annotations


class ControlledWorkflowError(Exception):
    """A safe, stable workflow failure without provider or input detail."""

    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class ProviderUnavailableError(ControlledWorkflowError):
    """Raised when a configured model provider cannot be used safely."""

    def __init__(self) -> None:
        super().__init__("provider_unavailable", retryable=True)


class PromptNotConfiguredError(ControlledWorkflowError):
    """Raised when a server-owned prompt cannot be resolved."""

    def __init__(self) -> None:
        super().__init__("prompt_not_configured")


class InvalidModelOutputError(ControlledWorkflowError):
    """Raised when a provider result does not match the declared schema."""

    def __init__(self) -> None:
        super().__init__("invalid_model_output")
