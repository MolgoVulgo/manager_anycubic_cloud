from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os

from accloud.endpoints import BASE_URL


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class RetryConfig:
    max_attempts: int = 3
    base_delay_s: float = 0.5
    max_delay_s: float = 5.0


@dataclass(frozen=True, slots=True)
class AppConfig:
    base_url: str = BASE_URL
    user_agent: str = "manager-anycubic-cloud/0.1.0"
    timeout_s: float = 20.0
    session_path: Path = Path.home() / ".config" / "acm" / "session.json"
    http_log_path: Path = Path("accloud_http.log")
    http_log_retention_days: int = 14
    fault_log_path: Path = Path("accloud_fault.log")
    retry: RetryConfig = field(default_factory=RetryConfig)
    pool_kind: str = "threads"
    workers: int = 4
    enable_fault_handler: bool = True
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "AppConfig":
        defaults = cls()
        max_attempts = int(os.getenv("ACCLOUD_RETRY_MAX_ATTEMPTS", "3"))
        base_delay_s = float(os.getenv("ACCLOUD_RETRY_BASE_DELAY_S", "0.5"))
        max_delay_s = float(os.getenv("ACCLOUD_RETRY_MAX_DELAY_S", "5.0"))

        return cls(
            base_url=os.getenv("ACCLOUD_BASE_URL", defaults.base_url),
            user_agent=os.getenv("ACCLOUD_USER_AGENT", defaults.user_agent),
            timeout_s=float(os.getenv("ACCLOUD_TIMEOUT_S", str(defaults.timeout_s))),
            session_path=Path(os.getenv("ACCLOUD_SESSION_PATH", str(defaults.session_path))),
            http_log_path=Path(os.getenv("ACCLOUD_HTTP_LOG_PATH", str(defaults.http_log_path))),
            http_log_retention_days=max(
                1,
                int(os.getenv("ACCLOUD_HTTP_LOG_RETENTION_DAYS", str(defaults.http_log_retention_days))),
            ),
            fault_log_path=Path(os.getenv("ACCLOUD_FAULT_LOG_PATH", str(defaults.fault_log_path))),
            retry=RetryConfig(
                max_attempts=max(1, max_attempts),
                base_delay_s=max(0.0, base_delay_s),
                max_delay_s=max(0.0, max_delay_s),
            ),
            pool_kind=os.getenv("ACCLOUD_POOL_KIND", defaults.pool_kind),
            workers=max(1, int(os.getenv("ACCLOUD_WORKERS", str(defaults.workers)))),
            enable_fault_handler=_env_bool("ACCLOUD_ENABLE_FAULT_HANDLER", defaults.enable_fault_handler),
            log_level=os.getenv("ACCLOUD_LOG_LEVEL", defaults.log_level).upper(),
        )
