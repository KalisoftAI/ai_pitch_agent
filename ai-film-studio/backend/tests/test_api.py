import io
import time

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mock_ai"] is True
    assert body["gcs_enabled"] is False
    assert body["gcs_bucket"] == "sales-crm"


def test_seeded_dashboard(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["projects_total"] >= 3
    assert len(body["categories"]) == 3
    assert body["recent_projects"]


def test_project_lifecycle(client: TestClient, project: dict) -> None:
    project_id = project["id"]
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 200

    updated = client.patch(
        f"/api/v1/projects/{project_id}", json={"title": "Renamed project"}
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Renamed project"

    progress = client.post(
        f"/api/v1/projects/{project_id}/progress",
        json={"current_step": "script", "status": "scripting"},
    )
    assert progress.status_code == 200
    assert progress.json()["current_step"] == "script"


def test_script_and_storyboard_flow(client: TestClient, project: dict) -> None:
    project_id = project["id"]

    assert client.get(f"/api/v1/projects/{project_id}/script").status_code == 404
    generated = client.post(
        f"/api/v1/projects/{project_id}/script/generate",
        json={"tone": "confident", "audience": "owners"},
    )
    assert generated.status_code == 200
    script = generated.json()
    assert script["content"]
    assert script["approved"] is False

    saved = client.put(
        f"/api/v1/projects/{project_id}/script",
        json={"content": "A sharper opening paragraph.\n\nA concrete example follows."},
    )
    assert saved.status_code == 200
    assert saved.json()["version"] == 2

    paragraph = client.post(
        f"/api/v1/projects/{project_id}/script/regenerate-paragraph",
        json={"paragraph_index": 0},
    )
    assert paragraph.status_code == 200

    approved = client.post(
        f"/api/v1/projects/{project_id}/script/approve", json={"approved": True}
    )
    assert approved.status_code == 200
    assert approved.json()["approved"] is True

    storyboard = client.post(
        f"/api/v1/projects/{project_id}/storyboard/generate",
        json={"scene_count": 5},
    )
    assert storyboard.status_code == 200
    scenes = storyboard.json()["scenes"]
    assert len(scenes) == 5

    scene_id = scenes[0]["id"]
    edited = client.patch(
        f"/api/v1/projects/{project_id}/storyboard/scenes/{scene_id}",
        json={"title": "New hook", "duration_seconds": 6},
    )
    assert edited.status_code == 200
    assert edited.json()["title"] == "New hook"

    regenerated = client.post(
        f"/api/v1/projects/{project_id}/storyboard/scenes/{scene_id}/regenerate",
        json={"instruction": "Make it more direct."},
    )
    assert regenerated.status_code == 200

    reordered = client.post(
        f"/api/v1/projects/{project_id}/storyboard/scenes/reorder",
        json={"scenes": [{"id": scene["id"], "order_index": index} for index, scene in enumerate(reversed(scenes))]},
    )
    assert reordered.status_code == 200

    approved_board = client.post(
        f"/api/v1/projects/{project_id}/storyboard/approve", json={"approved": True}
    )
    assert approved_board.status_code == 200
    assert approved_board.json()["approved"] is True


def test_render_flow(client: TestClient, project: dict) -> None:
    project_id = project["id"]
    client.post(f"/api/v1/projects/{project_id}/script/generate", json={})
    client.post(f"/api/v1/projects/{project_id}/script/approve", json={"approved": True})
    client.post(f"/api/v1/projects/{project_id}/storyboard/generate", json={"scene_count": 3})
    client.post(f"/api/v1/projects/{project_id}/storyboard/approve", json={"approved": True})

    created = client.post(
        f"/api/v1/projects/{project_id}/renders",
        json={
            "quality": "preview",
            "include_captions": True,
            "engine": "motion",
            "motion_style": "isometric",
            "effects": ["grain", "vignette"],
            "audio": False,
            "scene_patterns": {"0": "isometric"},
        },
    )
    assert created.status_code == 201, created.text
    job = created.json()
    assert job["status"] in {"queued", "running", "completed"}
    assert job["options"]["motion_style"] == "isometric"
    assert job["options"]["scene_patterns"] == {"0": "isometric"}

    for _ in range(40):
        current = client.get(f"/api/v1/renders/{job['id']}").json()
        if current["status"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.25)

    assert current["status"] == "completed", current
    assert current["progress"] == 100
    logs = client.get(f"/api/v1/renders/{job['id']}/logs")
    assert logs.status_code == 200
    assert logs.json()["logs"]


def test_render_requires_storyboard(client: TestClient, project: dict) -> None:
    response = client.post(
        f"/api/v1/projects/{project['id']}/renders",
        json={"quality": "preview"},
    )
    assert response.status_code == 400
    assert "storyboard" in response.json()["detail"].lower()


def test_render_requires_approved_storyboard(client: TestClient, project: dict) -> None:
    project_id = project["id"]
    client.post(f"/api/v1/projects/{project_id}/script/generate", json={})
    client.post(f"/api/v1/projects/{project_id}/script/approve", json={"approved": True})
    client.post(f"/api/v1/projects/{project_id}/storyboard/generate", json={"scene_count": 3})

    response = client.post(
        f"/api/v1/projects/{project_id}/renders",
        json={"quality": "preview"},
    )
    assert response.status_code == 400
    assert "approve" in response.json()["detail"].lower()


def test_ai_generation_and_usage(client: TestClient) -> None:
    models = client.get("/api/v1/ai/models")
    assert models.status_code == 200
    assert any(model["id"] == "mock-ai" for model in models.json())

    generated = client.post(
        "/api/v1/ai/generate",
        json={"task": "script", "prompt": "Write a hook about invoices", "max_tokens": 100},
    )
    assert generated.status_code == 200
    assert generated.json()["provider"] == "mock"

    usage = client.get("/api/v1/ai/usage")
    assert usage.status_code == 200
    assert usage.json()["total_requests"] >= 1


def test_assets_upload_and_delete(client: TestClient) -> None:
    upload = client.post(
        "/api/v1/assets",
        files={"file": ("pixel.png", io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "image/png")},
        data={"tags": "brand,test"},
    )
    assert upload.status_code == 201, upload.text
    asset = upload.json()
    assert asset["tags"] == ["brand", "test"]

    listed = client.get("/api/v1/assets", params={"tag": "brand"})
    assert listed.status_code == 200
    assert any(item["id"] == asset["id"] for item in listed.json())

    favorite = client.patch(f"/api/v1/assets/{asset['id']}", json={"favorite": True})
    assert favorite.status_code == 200
    assert favorite.json()["favorite"] is True

    deleted = client.delete(f"/api/v1/assets/{asset['id']}")
    assert deleted.status_code == 204


def test_storage_status_is_safe_when_disabled(client: TestClient) -> None:
    status = client.get("/api/v1/storage/status")
    assert status.status_code == 200
    body = status.json()
    assert body["enabled"] is False
    assert body["available"] is False
    assert body["bucket"] == "sales-crm"

    gallery = client.get("/api/v1/storage/gallery")
    assert gallery.status_code == 503


def test_topics(client: TestClient) -> None:
    categories = client.get("/api/v1/topics/categories")
    assert categories.status_code == 200
    assert {item["id"] for item in categories.json()} == {
        "business-tips",
        "erp-walkthrough",
        "financial-education",
    }

    suggestions = client.get("/api/v1/topics/suggest", params={"category": "business-tips"})
    assert suggestions.status_code == 200
    assert suggestions.json()

    custom = client.post(
        "/api/v1/topics/custom",
        json={"category": "business-tips", "title": "A custom topic"},
    )
    assert custom.status_code == 201
    assert custom.json()["is_custom"] is True
