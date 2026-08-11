from app.security import constant_time_key_matches, issue_ingestion_key, redact_attributes, redact_text


def test_ingestion_key_is_one_way_and_verifiable():
    raw, prefix, digest = issue_ingestion_key()
    assert raw.startswith(prefix + ".")
    assert constant_time_key_matches(raw, digest)
    assert not constant_time_key_matches(raw + "x", digest)
    assert raw not in digest


def test_redacts_sensitive_attributes_and_values():
    clean = redact_attributes({"http.method": "GET", "http.authorization": "Bearer abcdefghijk", "note": "api_key=abcdefghijk"})
    assert clean["http.method"] == "GET"
    assert clean["http.authorization"] == "[REDACTED]"
    assert "abcdefghijk" not in clean["note"]
    assert "secret-token-value" not in redact_text("Bearer secret-token-value")
