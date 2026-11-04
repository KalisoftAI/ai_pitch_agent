from sales_fastapi.governance import pii


def test_detects_email_and_phone():
    text = "Reach Ravi at ravi.k@example.co.in or +91 9876543210."
    found = pii.kinds(text)
    assert "EMAIL" in found
    assert "PHONE" in found


def test_detects_indian_pan_and_aadhaar():
    text = "PAN ABCDE1234F and Aadhaar 2345 6789 0123."
    found = pii.kinds(text)
    assert "PAN" in found
    assert "AADHAAR" in found


def test_redact_replaces_pii_with_tokens():
    out = pii.redact("email a@b.com phone 9876543210")
    assert "[EMAIL]" in out
    assert "[PHONE]" in out
    assert "a@b.com" not in out


def test_luhn_filters_random_16_digits():
    # Not a valid card number -> must not be reported as CARD.
    assert "CARD" not in pii.kinds("order 1234 5678 9012 3456")


def test_redact_structured_nested():
    payload = {"contact": {"email": "x@y.com"}, "list": ["call 9876543210"]}
    cleaned = pii.redact_structured(payload)
    assert "[EMAIL]" in cleaned["contact"]["email"]
    assert "[PHONE]" in cleaned["list"][0]


def test_mask_keeps_domain_visible():
    masked = pii.mask("sharma@kalisoftai.com")
    assert masked.endswith("@kalisoftai.com")
    assert "sharma" not in masked
