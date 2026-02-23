"""Source of truth for API routes."""

from __future__ import annotations

from dataclasses import dataclass


BASE_URL = "https://cloud-universe.anycubic.com"


@dataclass(frozen=True, slots=True)
class Endpoint:
    method: str
    path: str


ENDPOINTS: dict[str, Endpoint] = {
    "oauth_authorize": Endpoint(method="GET", path="https://uc.makeronline.com/login/oauth/authorize"),
    "oauth_logout": Endpoint(method="GET", path="https://uc.makeronline.com/api/logout"),
    "oauth_token_exchange": Endpoint(method="GET", path="/p/p/workbench/api/v3/public/getoauthToken"),
    "login_with_access_token": Endpoint(method="POST", path="/p/p/workbench/api/v3/public/loginWithAccessToken"),
    "session_validate": Endpoint(method="POST", path="/p/p/workbench/api/work/index/getUserStore"),
    "quota": Endpoint(method="POST", path="/p/p/workbench/api/work/index/getUserStore"),
    "files": Endpoint(method="POST", path="/p/p/workbench/api/work/index/files"),
    "files_alt": Endpoint(method="POST", path="/p/p/workbench/api/work/index/userFiles"),
    "download": Endpoint(method="POST", path="/p/p/workbench/api/work/index/getDowdLoadUrl"),
    "delete": Endpoint(method="POST", path="/p/p/workbench/api/work/index/delFiles"),
    "rename_file": Endpoint(method="POST", path="/p/p/workbench/api/work/index/renameFile"),
    "upload_status": Endpoint(method="POST", path="/p/p/workbench/api/work/index/getUploadStatus"),
    "gcode_info": Endpoint(method="GET", path="/p/p/workbench/api/api/work/gcode/info"),
    "upload_lock": Endpoint(method="POST", path="/p/p/workbench/api/v2/cloud_storage/lockStorageSpace"),
    "upload_register": Endpoint(method="POST", path="/p/p/workbench/api/v2/profile/newUploadFile"),
    "upload_unlock": Endpoint(method="POST", path="/p/p/workbench/api/v2/cloud_storage/unlockStorageSpace"),
    "print_order": Endpoint(method="POST", path="/p/p/workbench/api/work/operation/sendOrder"),
    "printers": Endpoint(method="GET", path="/p/p/workbench/api/work/printer/getPrinters"),
    "printer_info": Endpoint(method="POST", path="/p/p/workbench/api/work/printer/Info"),
}


def endpoint_path(name: str, **params: str) -> str:
    endpoint = ENDPOINTS[name]
    return endpoint.path.format(**params)
