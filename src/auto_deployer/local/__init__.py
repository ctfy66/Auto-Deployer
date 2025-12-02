"""Local execution module for deploying on the current machine."""

from .session import LocalSession, LocalCommandResult
from .probe import LocalProbe, LocalHostFacts

__all__ = ["LocalSession", "LocalCommandResult", "LocalProbe", "LocalHostFacts"]
