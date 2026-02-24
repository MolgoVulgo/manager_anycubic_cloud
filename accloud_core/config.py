from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os

from accloud_core.endpoints import BASE_URL


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
    region: str = "global"
    device_id: str = "manager-anycubic-cloud-dev"
    client_version: str = "0.1.0"
    public_version: str = "1.0.0"
    public_device_type: str = "web"
    public_is_cn: str = "2"
    public_app_id: str = "f9b3528877c94d5c9c5af32245db46ef"
    public_app_secret: str = "0cf75926606049a3937f56b0373b99fb"
    timeout_s: float = 20.0
    session_path: Path = Path("session.json")
    cache_dir: Path = Path.home() / ".cache" / "acm"
    cache_startup_ttl_s: int = 600
    cache_gcode_ttl_s: int = 86400
    cache_thumbnail_ttl_s: int = 86400 * 7
    log_dir: Path = Path(".accloud") / "logs"
    app_log_path: Path = Path(".accloud") / "logs" / "accloud_app.log"
    http_log_path: Path = Path(".accloud") / "logs" / "accloud_http.log"
    render3d_log_path: Path = Path(".accloud") / "logs" / "accloud_render3d.log"
    fault_log_path: Path = Path(".accloud") / "logs" / "accloud_fault.log"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backups: int = 5
    log_compress: bool = True
    log_compress_level: int = 6
    retry: RetryConfig = field(default_factory=RetryConfig)
    pool_kind: str = "threads"
    workers: int = 4
    enable_fault_handler: bool = True
    log_level: str = "INFO"
    http_log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "AppConfig":
        defaults = cls()
        max_attempts = int(os.getenv("ACCLOUD_RETRY_MAX_ATTEMPTS", "3"))
        base_delay_s = float(os.getenv("ACCLOUD_RETRY_BASE_DELAY_S", "0.5"))
        max_delay_s = float(os.getenv("ACCLOUD_RETRY_MAX_DELAY_S", "5.0"))
        log_dir = Path(os.getenv("ACCLOUD_LOG_DIR", str(defaults.log_dir)))
        app_log_path = Path(
            os.getenv(
                "ACCLOUD_APP_LOG_PATH",
                str(log_dir / "accloud_app.log"),
            )
        )
        http_log_path = Path(
            os.getenv(
                "ACCLOUD_HTTP_LOG_PATH",
                str(log_dir / "accloud_http.log"),
            )
        )
        render3d_log_path = Path(
            os.getenv(
                "ACCLOUD_RENDER3D_LOG_PATH",
                str(log_dir / "accloud_render3d.log"),
            )
        )
        fault_log_path = Path(
            os.getenv(
                "ACCLOUD_FAULT_LOG_PATH",
                str(log_dir / "accloud_fault.log"),
            )
        )
        legacy_backups = max(
            1,
            int(os.getenv("ACCLOUD_HTTP_LOG_RETENTION_DAYS", str(defaults.log_backups))),
        )
        log_backups = max(
            1,
            int(os.getenv("ACCLOUD_LOG_BACKUPS", str(legacy_backups))),
        )
        log_max_bytes = max(
            1,
            int(os.getenv("ACCLOUD_LOG_MAX_BYTES", str(defaults.log_max_bytes))),
        )
        log_compress_level = max(
            1,
            min(9, int(os.getenv("ACCLOUD_LOG_COMPRESS_LEVEL", str(defaults.log_compress_level)))),
        )

        return cls(
            base_url=os.getenv("ACCLOUD_BASE_URL", defaults.base_url),
            user_agent=os.getenv("ACCLOUD_USER_AGENT", defaults.user_agent),
            region=os.getenv("ACCLOUD_REGION", defaults.region),
            device_id=os.getenv("ACCLOUD_DEVICE_ID", defaults.device_id),
            client_version=os.getenv("ACCLOUD_CLIENT_VERSION", defaults.client_version),
            public_version=os.getenv("ACCLOUD_PUBLIC_VERSION", defaults.public_version),
            public_device_type=os.getenv("ACCLOUD_PUBLIC_DEVICE_TYPE", defaults.public_device_type),
            public_is_cn=os.getenv("ACCLOUD_PUBLIC_IS_CN", defaults.public_is_cn),
            public_app_id=os.getenv("ACCLOUD_PUBLIC_APP_ID", defaults.public_app_id),
            public_app_secret=os.getenv("ACCLOUD_PUBLIC_APP_SECRET", defaults.public_app_secret),
            timeout_s=float(os.getenv("ACCLOUD_TIMEOUT_S", str(defaults.timeout_s))),
            session_path=Path(os.getenv("ACCLOUD_SESSION_PATH", str(defaults.session_path))),
            cache_dir=Path(os.getenv("ACCLOUD_CACHE_DIR", str(defaults.cache_dir))),
            cache_startup_ttl_s=max(
                0,
                int(os.getenv("ACCLOUD_CACHE_STARTUP_TTL_S", str(defaults.cache_startup_ttl_s))),
            ),
            cache_gcode_ttl_s=max(
                0,
                int(os.getenv("ACCLOUD_CACHE_GCODE_TTL_S", str(defaults.cache_gcode_ttl_s))),
            ),
            cache_thumbnail_ttl_s=max(
                0,
                int(os.getenv("ACCLOUD_CACHE_THUMBNAIL_TTL_S", str(defaults.cache_thumbnail_ttl_s))),
            ),
            log_dir=log_dir,
            app_log_path=app_log_path,
            http_log_path=http_log_path,
            render3d_log_path=render3d_log_path,
            fault_log_path=fault_log_path,
            log_max_bytes=log_max_bytes,
            log_backups=log_backups,
            log_compress=_env_bool("ACCLOUD_LOG_COMPRESS", defaults.log_compress),
            log_compress_level=log_compress_level,
            retry=RetryConfig(
                max_attempts=max(1, max_attempts),
                base_delay_s=max(0.0, base_delay_s),
                max_delay_s=max(0.0, max_delay_s),
            ),
            pool_kind=os.getenv("ACCLOUD_POOL_KIND", defaults.pool_kind),
            workers=max(1, int(os.getenv("ACCLOUD_WORKERS", str(defaults.workers)))),
            enable_fault_handler=_env_bool("ACCLOUD_ENABLE_FAULT_HANDLER", defaults.enable_fault_handler),
            log_level=os.getenv("ACCLOUD_LOG_LEVEL", defaults.log_level).upper(),
            http_log_level=os.getenv("ACCLOUD_HTTP_LOG_LEVEL", defaults.http_log_level).upper(),
        )
