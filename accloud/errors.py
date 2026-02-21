from __future__ import annotations


class CloudError(RuntimeError):
    """Base class for cloud-related failures."""


class CloudTransportError(CloudError):
    """HTTP transport-level failure."""


class CloudApiError(CloudError):
    """HTTP/API semantic failure."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code

