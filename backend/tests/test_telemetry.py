from app.telemetry import normalize_otlp_json


def test_normalizes_and_redacts_otlp_trace():
    payload = {"resourceSpans": [{"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "api"}}]}, "scopeSpans": [{"spans": [{"traceId": "t1", "spanId": "s1", "name": "GET /", "startTimeUnixNano": "1000000", "endTimeUnixNano": "4000000", "attributes": [{"key": "authorization", "value": {"stringValue": "Bearer abcdefghijk"}}]}]}]}]}
    rows, warnings = normalize_otlp_json("traces", payload)
    assert not warnings
    assert rows[0]["service"] == "api"
    assert rows[0]["attributes"]["authorization"] == "[REDACTED]"
