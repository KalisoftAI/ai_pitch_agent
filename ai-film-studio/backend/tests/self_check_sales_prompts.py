"""Self-check for the read-only sales prompt catalog API."""
import os
import sys

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://test:test@localhost/test")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.routers import sales_prompts
from app.services import sales_prompt_catalog
from app.services.sales_prompt_catalog import Prompt
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    sample = Prompt(
        id="PR-00",
        task="self_check",
        model="gemini-2.5-flash",
        tier="small",
        json_mode=True,
        human_review=True,
        template="Return JSON for {text}",
        variables=("text",),
        sample_input={"text": "ok"},
        expected_output={"result": "ok"},
    )
    check(sample.to_dict()["variables"] == ["text"], "Prompt.to_dict must be JSON-safe")

    prompts = sales_prompt_catalog.catalog()
    check(len(prompts) == 5, f"expected 5 published prompts, got {len(prompts)}")
    check(all(isinstance(prompt, Prompt) for prompt in prompts), "catalog must hold Prompt records")

    prompt = sales_prompt_catalog.get_prompt(" PR-01 ")
    check(prompt.task == "customer_feedback_summary", "get_prompt must trim and match ids")

    try:
        sales_prompt_catalog.get_prompt("PR-99")
    except HTTPException as exc:
        check(exc.status_code == 404, "unknown prompt must raise HTTPException 404")
    else:
        raise AssertionError("unknown prompt must raise HTTPException 404")

    check(
        len(sales_prompt_catalog.list_prompts(human_review=False)) == 1,
        "human_review filter must return exactly PR-03",
    )
    check(
        len(sales_prompt_catalog.list_prompts(model="gemma-4-27b-it")) == 2,
        "model filter must return the two gemma prompts",
    )
    check(
        len(sales_prompt_catalog.list_prompts(task="journey_next_step")) == 1,
        "task filter must return exactly PR-02",
    )

    write_methods = {
        method
        for route in sales_prompts.router.routes
        for method in getattr(route, "methods", set())
        if method not in {"GET", "HEAD", "OPTIONS"}
    }
    check(not write_methods, f"catalog router must be read-only, found {write_methods}")

    app = FastAPI()
    app.include_router(sales_prompts.router)
    with TestClient(app) as client:
        listing = client.get("/sales-prompts")
        check(listing.status_code == 200, "GET /sales-prompts must return 200")
        body = listing.json()
        check(len(body["prompts"]) == 5, "GET /sales-prompts must list all prompts")
        check(body["meta"]["version"] == "2026-10-30.1", "catalog version must be published")
        check(body["meta"]["total"] == 5, "meta.total must match returned prompts")
        check("human_review_required" in body["meta"], "meta must expose review policy")

        detail = client.get("/sales-prompts/PR-05")
        check(detail.status_code == 200, "GET /sales-prompts/PR-05 must return 200")
        check(detail.json()["task"] == "dispatch_followup_draft", "detail must match PR-05")

        missing = client.get("/sales-prompts/PR-99")
        check(missing.status_code == 404, "unknown id must return 404 JSON")

        filtered = client.get("/sales-prompts", params={"human_review": "false"})
        check(
            [item["id"] for item in filtered.json()["prompts"]] == ["PR-03"],
            "filtered JSON response must contain only PR-03",
        )

        for method in ("post", "put", "patch"):
            response = getattr(client, method)("/sales-prompts", json={})
            check(response.status_code == 405, f"{method.upper()} must not be allowed")
        check(client.delete("/sales-prompts").status_code == 405, "DELETE must not be allowed")

    print("self-check passed: read-only sales prompt catalog API is healthy")


if __name__ == "__main__":
    main()
