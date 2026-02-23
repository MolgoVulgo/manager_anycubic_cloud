from __future__ import annotations

from accloud_core.utils import redact_json_like, redact_mapping, safe_url_for_log


def test_redact_mapping_masks_xx_sensitive_headers() -> None:
    payload = {
        "XX-Token": "secret-token",
        "XX-Signature": "deadbeef",
        "XX-Nonce": "12345",
        "X-Request-Id": "req-1",
    }
    redacted = redact_mapping(payload)
    assert redacted["XX-Token"] == "<redacted>"
    assert redacted["XX-Signature"] == "<redacted>"
    assert redacted["XX-Nonce"] == "<redacted>"
    assert redacted["X-Request-Id"] == "req-1"


def test_redact_json_like_masks_nested_fragment_keys() -> None:
    payload = {
        "meta": {
            "printer_token": "abc",
            "upload_signature": "sig",
            "client_nonce_value": "nonce",
            "safe": "ok",
        }
    }
    redacted = redact_json_like(payload)
    assert redacted["meta"]["printer_token"] == "<redacted>"
    assert redacted["meta"]["upload_signature"] == "<redacted>"
    assert redacted["meta"]["client_nonce_value"] == "<redacted>"
    assert redacted["meta"]["safe"] == "ok"


def test_safe_url_for_log_masks_token_signature_and_nonce_query_keys() -> None:
    safe = safe_url_for_log(
        "https://example.test/path?token=abc&XX-Signature=deadbeef&nonce=123&q=ok"
    )
    assert "token=%3Credacted%3E" in safe
    assert "XX-Signature=%3Credacted%3E" in safe
    assert "nonce=%3Credacted%3E" in safe
    assert "q=ok" in safe
