from __future__ import annotations

import logging
import os


LOGGER_POLICY = logging.getLogger("render3d.parallel")
RENDER3D_PARALLEL_POLICY_ENV = "RENDER3D_PARALLEL_POLICY"
_VALID_POLICIES = {"python_fanout", "cpp_internal", "auto"}
_WARNED_INVALID = False


def resolve_parallel_policy() -> str:
    global _WARNED_INVALID
    raw = os.getenv(RENDER3D_PARALLEL_POLICY_ENV, "python_fanout")
    value = str(raw or "").strip().lower()
    if value in {"", "auto"}:
        return "python_fanout"
    if value in _VALID_POLICIES:
        return value
    if not _WARNED_INVALID:
        _WARNED_INVALID = True
        LOGGER_POLICY.warning(
            "Unknown %s=%r, fallback to python_fanout",
            RENDER3D_PARALLEL_POLICY_ENV,
            raw,
        )
    return "python_fanout"


def uses_python_fanout() -> bool:
    return resolve_parallel_policy() == "python_fanout"
