from __future__ import annotations

from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
import threading
from typing import Any, Protocol


class ProgressCallback(Protocol):
    def __call__(self, percent: int, stage: str) -> None: ...


class CancelledError(RuntimeError):
    pass


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise CancelledError("Task cancelled")


class TaskRunner:
    """Shared async runner skeleton for build tasks."""

    def __init__(self, pool_kind: str = "threads", workers: int = 4) -> None:
        self._pool_kind = pool_kind
        self._workers = max(1, workers)
        if pool_kind == "processes":
            self._executor: ThreadPoolExecutor | ProcessPoolExecutor = ProcessPoolExecutor(max_workers=self._workers)
        else:
            self._executor = ThreadPoolExecutor(max_workers=self._workers)

    @property
    def pool_kind(self) -> str:
        return self._pool_kind

    @property
    def workers(self) -> int:
        return self._workers

    def submit(self, fn: Any, *args: Any, **kwargs: Any) -> Future[Any]:
        return self._executor.submit(fn, *args, **kwargs)

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)

    def __enter__(self) -> "TaskRunner":
        return self

    def __exit__(self, exc_type: object, exc: BaseException | None, tb: object) -> None:
        self.shutdown(wait=True, cancel_futures=False)

