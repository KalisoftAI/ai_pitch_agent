"""Tests for the refined outreach workflow helpers and endpoints."""

from sales_fastapi.contact_validation import normalize_email, normalize_phone
from sales_fastapi.outreach_forms import with_contact_context


def test_contact_normalization_selects_first_usable_address():
    raw = "\u200babhi.admin@abhishekindustry.com\u200b;\nsecond@example.com"
    assert normalize_email(raw) == "abhi.admin@abhishekindustry.com"
    assert normalize_phone("+91 (98765) 43210") == "919876543210"
    assert normalize_email("not-an-email") == ""


def test_form_links_append_contact_context_only_to_http_links():
    url = with_contact_context(
        "https://example.test/feedback?source=outreach",
        {"contact_name": "Ravi Shah", "company": "Acme Films", "email": "ravi@acme.example"},
    )
    assert "source=outreach" in url
    assert "contact_name=Ravi+Shah" in url
    assert "company=Acme+Films" in url
    assert "email=ravi%40acme.example" in url
    assert (
        with_contact_context("mailto:sales@example.test", {"company": "Acme"})
        == "mailto:sales@example.test"
    )


def test_normalize_emails_endpoint_is_syntax_only(client, auth_headers):
    from sales_fastapi.database import SessionLocal
    from sales_fastapi.models import MarketingCompany, User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "tester@kalisoftai.com").one()
        row = MarketingCompany(
            user_id=user.id,
            company="Acme Films",
            company_key="acme-films",
            email="\u200bFIRST@EXAMPLE.COM\u200b; second@example.com",
            phone="9876543210",
        )
        db.add(row)
        db.commit()
        row_id = row.id
    finally:
        db.close()

    result = client.post("/api/marketing-companies/normalize-emails", headers=auth_headers)
    assert result.status_code == 200, result.text
    assert result.json()["normalized"] == 1
    assert result.json()["verification_changed"] == 0

    rows = client.get("/api/marketing-companies", headers=auth_headers).json()
    assert next(item for item in rows if item["id"] == row_id)["email"] == "first@example.com"


def test_channel_filter_uses_valid_contact_details(client, auth_headers):
    from sales_fastapi.database import SessionLocal
    from sales_fastapi.models import MarketingCompany, User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "tester@kalisoftai.com").one()
        db.add_all(
            [
                MarketingCompany(
                    user_id=user.id,
                    company="Email Co",
                    company_key="email-co",
                    email="ok@example.com",
                    phone="123",
                ),
                MarketingCompany(
                    user_id=user.id,
                    company="WhatsApp Co",
                    company_key="whatsapp-co",
                    email="bad",
                    phone="9876543210",
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    email_rows = client.get("/api/marketing-companies?channel=email", headers=auth_headers).json()
    phone_rows = client.get(
        "/api/marketing-companies?channel=whatsapp", headers=auth_headers
    ).json()
    assert [row["company"] for row in email_rows] == ["Email Co"]
    assert [row["company"] for row in phone_rows] == ["WhatsApp Co"]


def test_customer_form_links_and_submissions(client, auth_headers):
    public = client.get("/api/forms/config")
    assert public.status_code == 200
    assert public.json()["source"] == "default"

    saved = client.put(
        "/api/outreach-forms/links",
        headers=auth_headers,
        json={
            "feedback_url": "https://example.test/feedback",
            "review_url": "https://example.test/review",
            "meeting_url": "mailto:sales@example.test",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["source"] == "custom"
    assert client.get("/api/forms/config").json()["feedback_url"] == "https://example.test/feedback"

    feedback = client.post(
        "/api/public/forms/feedback",
        json={
            "name": "Ravi",
            "email": "ravi@acme.example",
            "phone": "9876543210",
            "message": "Good service",
        },
    )
    review = client.post(
        "/api/public/forms/review",
        json={
            "name": "Anita",
            "email": "anita@acme.example",
            "rating": 5,
            "title": "Strong film",
            "message": "Excellent quality",
        },
    )
    assert feedback.status_code == 201, feedback.text
    assert review.status_code == 201, review.text
    assert feedback.json()["category"] == "customer_feedback"
    assert review.json()["category"] == "product_review"

    submissions = client.get("/api/outreach-forms/submissions", headers=auth_headers)
    assert submissions.status_code == 200, submissions.text
    categories = {item["category"] for item in submissions.json()}
    assert {"customer_feedback", "product_review"} <= categories
