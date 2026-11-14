from __future__ import annotations


class RecursionError_(Exception):
    """Base class for domain errors."""


class NotFound(RecursionError_):
    pass


class InvalidCommand(RecursionError_):
    pass


class ValidationFailed(RecursionError_):
    pass


class ProviderError(RecursionError_):
    pass


class ProviderUnavailable(ProviderError):
    pass
