"""Source of truth for API routes (phase 1 placeholder)."""

BASE_URL = "https://api.anycubic.example"

ENDPOINTS: dict[str, dict[str, str]] = {
    "quota": {"method": "GET", "path": "/quota"},
    "files": {"method": "GET", "path": "/files"},
    "file_details": {"method": "GET", "path": "/files/{file_id}"},
    "gcode_info": {"method": "GET", "path": "/files/{file_id}/gcode"},
    "download": {"method": "GET", "path": "/files/{file_id}/download"},
    "upload": {"method": "POST", "path": "/files/upload"},
    "delete": {"method": "DELETE", "path": "/files/{file_id}"},
    "print_order": {"method": "POST", "path": "/print/orders"},
    "printers": {"method": "GET", "path": "/printers"},
}

