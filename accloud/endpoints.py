"""Source of truth for API routes (phase 3 baseline)."""

from __future__ import annotations

from dataclasses import dataclass


BASE_URL = "https://api.anycubic.example"


@dataclass(frozen=True, slots=True)
class Endpoint:
    method: str
    path: str


ENDPOINTS: dict[str, Endpoint] = {
    "quota": Endpoint(method="GET", path="/quota"),
    "files": Endpoint(method="GET", path="/files"),
    "file_details": Endpoint(method="GET", path="/files/{file_id}"),
    "gcode_info": Endpoint(method="GET", path="/files/{file_id}/gcode"),
    "download": Endpoint(method="GET", path="/files/{file_id}/download"),
    "upload": Endpoint(method="POST", path="/files/upload"),
    "delete": Endpoint(method="DELETE", path="/files/{file_id}"),
    "print_order": Endpoint(method="POST", path="/print/orders"),
    "printers": Endpoint(method="GET", path="/printers"),
}


def endpoint_path(name: str, **params: str) -> str:
    endpoint = ENDPOINTS[name]
    return endpoint.path.format(**params)

