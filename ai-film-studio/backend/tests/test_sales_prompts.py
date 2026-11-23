import pytest
from app.routers import sales_prompts
from app.services.sales_prompt_catalog import Prompt, get_prompt, list_prompts
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(sales_prompts.router)
    return TestClient(app)


def test_catalog_is_published_snapshot():
    prompts = list_prompts()
    assert len(prompts) == 5
    assert [prompt.id for prompt in prompts] == ["PR-01", "PR-02", "PR-03", "PR-04", "PR-05"]
    assert all(isinstance(prompt, Prompt) for prompt in prompts)


def test_lookup_is_case_insensitive_and_404_for_unknown(client: TestClient):
    assert get_prompt(" pr-01 ").task == "customer_feedback_summary"
    response = client.get("/sales-prompts/PR-99")
    assert response.status_code == 404
    assert response.json()["detail"] == "Prompt 'PR-99' not found"


def test_filters():
    assert [p.id for p in list_prompts(human_review=False)] == ["PR-03"]
    assert [p.id for p in list_prompts(model="gemma-4-27b-it")] == ["PR-01", "PR-05"]
    assert [p.id for p in list_prompts(task="weekly_prompt_refinement")] == ["PR-04"]


def test_api_json_contract(client: TestClient):
    response = client.get("/sales-prompts")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["version"] == "2026-10-30.1"
    assert body["meta"]["total"] == len(body["prompts"]) == 5
    first = body["prompts"][0]
    assert set(first) == {
        "id",
        "task",
        "model",
        "tier",
        "json_mode",
        "human_review",
        "template",
        "variables",
        "sample_input",
        "expected_output",
    }
    assert isinstance(first["variables"], list)


def test_api_detail_and_filters(client: TestClient):
    detail = client.get("/sales-prompts/PR-03")
    assert detail.status_code == 200
    assert detail.json()["human_review"] is False

    filtered = client.get("/sales-prompts", params={"human_review": "true"})
    assert [item["id"] for item in filtered.json()["prompts"]] == [
        "PR-01",
        "PR-02",
        "PR-04",
        "PR-05",
    ]


def test_api_is_read_only(client: TestClient):
    for method in ("post", "put", "patch"):
        response = getattr(client, method)("/sales-prompts", json={})
        assert response.status_code == 405
    assert client.delete("/sales-prompts").status_code == 405
