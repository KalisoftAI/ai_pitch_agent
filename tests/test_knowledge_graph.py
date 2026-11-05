from sales_fastapi.database import SessionLocal
from sales_fastapi.models import MarketingCompany, User


def _add_marketing_company():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "tester@kalisoftai.com").one()
        row = MarketingCompany(
            user_id=user.id,
            company="Acme Packagin",
            company_key="acme-packagin",
            funnel_stage="interest",
            requirements="Stretch film quote",
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def test_graph_build_review_chat_feedback_and_user_isolation(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setattr("sales_fastapi.routers.knowledge_graph.GCSStorage", lambda **kwargs: type("GCS", (), {"available": False})())
    monkeypatch.setattr(
        "sales_fastapi.routers.knowledge_graph._local_path",
        lambda user_id, filename="current.json": tmp_path / f"{user_id}-{filename}",
    )
    created = client.post(
        "/api/contacts",
        headers=auth_headers,
        json={"email": "buyer@acme.example", "company": "Acme Packaging", "name": "Buyer", "intent": "procurement"},
    )
    assert created.status_code == 201, created.text
    marketing_id = _add_marketing_company()

    built = client.post("/api/knowledge-graph/build", headers=auth_headers)
    assert built.status_code == 200, built.text
    payload = built.json()
    assert payload["stats"]["nodes"] > 0
    assert payload["stats"]["pending_edges"] > 0
    version = payload["version"]

    rebuilt = client.post("/api/knowledge-graph/build", headers=auth_headers).json()
    assert rebuilt["version"] == version

    graph = client.get("/api/knowledge-graph", headers=auth_headers).json()
    pending = next(edge for edge in graph["edges"] if edge["review_status"] == "pending")
    reviews = client.get("/api/knowledge-graph/reviews?status=pending", headers=auth_headers).json()
    review = next(item for item in reviews["items"] if item["edge_key"] == pending["edge_key"])
    decision = client.post(
        f"/api/knowledge-graph/reviews/{review['id']}",
        headers=auth_headers,
        json={"action": "accept", "note": "Confirmed during UAT."},
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "accepted"

    chat = client.post(
        "/api/knowledge-graph/chat",
        headers=auth_headers,
        json={"question": "Show relationships for Acme", "selected_node": pending["source"]},
    )
    assert chat.status_code == 200, chat.text
    assert chat.json()["cost_micros"] == 0
    assert chat.json()["graph_version"] == version

    feedback = client.post(
        "/api/knowledge-graph/feedback",
        headers=auth_headers,
        json={"graph_version": version, "question": "Which company is this?", "answer": chat.json()["reply"], "correction": "Acme is the account", "rating": 4},
    )
    assert feedback.status_code == 201, feedback.text
    assert feedback.json()["status"] == "pending_evaluation"

    other_token = client.post("/api/auth/google", json={"id_token": "dev:other@kalisoftai.com"}).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}
    other_graph = client.get("/api/knowledge-graph", headers=other_headers).json()
    assert other_graph["nodes"] == []
    assert other_graph["edges"] == []

    assert marketing_id > 0
