from datetime import datetime, timezone


def test_catalog_product_rate_quote_flow(client, auth_headers):
    product = client.post(
        "/api/catalog/products",
        headers=auth_headers,
        json={
            "name": "LD Film 50 micron",
            "category": "film",
            "unit": "kg",
            "description": "test product",
        },
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]

    rate = client.post(
        "/api/catalog/rates",
        headers=auth_headers,
        json={
            "product_id": product_id,
            "rate": 112.5,
            "notes": "daily rate",
        },
    )
    assert rate.status_code == 201, rate.text
    rate_id = rate.json()["id"]
    assert rate.json()["status"] == "pending"

    review = client.post(
        f"/api/catalog/rates/{rate_id}/review",
        headers=auth_headers,
        json={"decision": "approved", "notes": "approved"},
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "approved"

    quote = client.post(
        "/api/catalog/quote", headers=auth_headers, json={"product_id": product_id, "micron": 50}
    )
    assert quote.status_code == 200, quote.text
    body = quote.json()
    assert body["price"] > 0
    assert body["approved_rate_id"] == rate_id

    summary = client.get("/api/catalog/summary", headers=auth_headers)
    assert summary.status_code == 200
    assert summary.json()["products"] == 1
    assert summary.json()["approved_rates"] == 1


def test_team_update_review_and_send(client, auth_headers):
    created = client.post(
        "/api/team/messages",
        headers=auth_headers,
        json={
            "body": "Visited ACME; they asked for a 50 micron quote.",
            "kind": "field_update",
            "meta": {"company": "ACME"},
        },
    )
    assert created.status_code == 200, created.text
    message = created.json()
    assert message["status"] == "pending"

    edited = client.patch(
        f"/api/team/messages/{message['id']}",
        headers=auth_headers,
        json={"body": "Visited ACME; quote requested for 50 micron."},
    )
    assert edited.status_code == 200, edited.text
    assert "quote requested" in edited.json()["body"]

    review = client.post(
        f"/api/team/messages/{message['id']}/review",
        headers=auth_headers,
        json={"decision": "approved"},
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "approved"

    sent = client.post(f"/api/team/messages/{message['id']}/send", headers=auth_headers)
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "sent"

    notifications = client.get("/api/team/notifications", headers=auth_headers)
    assert notifications.status_code == 200
    assert notifications.json()["new_since_id"] >= message["id"]

    activity = client.get("/api/team/activity", headers=auth_headers)
    assert activity.status_code == 200
    assert activity.json()["by_status"]["sent"] == 1


def test_company_visits_and_followup_stats(client, auth_headers):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    created = client.post(
        "/api/visits",
        headers=auth_headers,
        json={
            "company": "ACME Packaging",
            "contact_name": "Ravi",
            "visit_date": today,
            "outcome": "quote_requested",
            "follow_up_date": today,
            "notes": "Discussed 50 micron film.",
        },
    )
    assert created.status_code == 201, created.text
    visit_id = created.json()["id"]

    updated = client.patch(
        f"/api/visits/{visit_id}",
        headers=auth_headers,
        json={"status": "follow_up", "next_action": "Send rate card"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["next_action"] == "Send rate card"

    rows = client.get("/api/visits", headers=auth_headers)
    assert rows.status_code == 200
    assert len(rows.json()) == 1

    stats = client.get("/api/visits/stats", headers=auth_headers)
    assert stats.status_code == 200
    assert stats.json()["visits"] == 1
    assert stats.json()["pending_followups"] == 1

    activity = client.get("/api/visits/activity", headers=auth_headers)
    assert activity.status_code == 200
    assert activity.json()["visits"] == 1


def test_user_management_admin_flow(client, auth_headers):
    created = client.post(
        "/api/users",
        headers=auth_headers,
        json={
            "email": "field.one",
            "name": "Field One",
            "password": "strong-pass-123",
            "role": "field",
        },
    )
    assert created.status_code == 201, created.text
    user = created.json()
    assert user["email"] == "field.one@kalika.local"
    assert user["role"] == "field"

    updated = client.patch(
        f"/api/users/{user['id']}",
        headers=auth_headers,
        json={"role": "sales", "name": "Field Sales"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["role"] == "sales"

    detail = client.get("/api/users/detail", headers=auth_headers)
    assert detail.status_code == 200
    assert any(item["id"] == user["id"] for item in detail.json())

    activity = client.get("/api/users/activity", headers=auth_headers)
    assert activity.status_code == 200
    assert any(item["id"] == user["id"] for item in activity.json()["users"])


def test_ai_and_social_status_are_data_driven(client, auth_headers):
    recs = client.get("/api/ai/recommendations", headers=auth_headers)
    assert recs.status_code == 200, recs.text
    body = recs.json()
    assert body["engine"] == "rules-v1"
    assert body["source"] == "live workspace database"
    assert "recommendations" in body
    assert "counts" in body

    analytics = client.get("/api/ai/communication-analytics", headers=auth_headers)
    assert analytics.status_code == 200, analytics.text
    assert analytics.json()["email"]["reply_tracking"] is False

    social = client.get("/api/social/overview", headers=auth_headers)
    assert social.status_code == 200, social.text
    assert "instagram" in social.json()
    assert "linkedin" in social.json()

    instagram = client.post("/api/social/instagram/sync", headers=auth_headers)
    assert instagram.status_code == 200, instagram.text
    assert instagram.json()["status"] == "configuration_required"
