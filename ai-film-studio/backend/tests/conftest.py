import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_ROOT = Path(tempfile.mkdtemp(prefix="ai-film-studio-tests-"))

os.environ["APP_MODE"] = "development"
os.environ["MOCK_AI"] = "true"
os.environ["SEED_SAMPLE_DATA"] = "true"
os.environ["RENDER_MODE"] = "simulated"
os.environ["GCS_ENABLED"] = "false"
os.environ["DATABASE_URL"] = f"sqlite:///{(TEST_ROOT / 'test.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(TEST_ROOT / "storage")
os.environ["AI_CACHE_TTL_SECONDS"] = "0"

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def project(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/projects",
        json={
            "title": "Test project",
            "category": "business-tips",
            "topic": "Why cash flow matters",
            "visual_style": "cinematic",
            "template": "insight",
            "duration_seconds": 30,
            "aspect_ratio": "16:9",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
