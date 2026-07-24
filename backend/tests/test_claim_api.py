from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def control_state(cookie: str) -> dict:
    response = client.get("/api/state", params={"cookie": cookie})
    assert response.status_code == 200
    return response.json()["state"]


def test_claim_draft_is_strict_cookie_scoped_and_preserves_unrelated_state() -> None:
    cookie = "claim-contract-a"
    seed = client.patch(
        "/api/state",
        params={"cookie": cookie},
        json={"data": {"evaluator_marker": {"keep": True}}, "note": "fixture"},
    )
    assert seed.status_code == 200

    draft = {
        "formData": {"insured-name": "Ada"},
        "uploadedFiles": [],
        "currentStep": 2,
    }
    response = client.put("/api/claims/draft", params={"cookie": cookie}, json=draft)
    assert response.status_code == 200
    assert response.json()["draft"]["formData"]["insured-name"] == "Ada"

    state = control_state(cookie)
    assert state["data"]["current_claim"]["currentStep"] == 2
    workspace = client.get("/api/claims/workspace", params={"cookie": cookie})
    assert workspace.status_code == 200
    assert workspace.json()["draft"]["formData"]["insured-name"] == "Ada"
    assert state["data"]["evaluator_marker"] == {"keep": True}
    assert control_state("claim-contract-b")["data"]["current_claim"] is None


def test_claim_draft_rejects_unknown_internal_fields_and_invalid_steps() -> None:
    valid = {"formData": {}, "uploadedFiles": [], "currentStep": 1}
    assert (
        client.put(
            "/api/claims/draft",
            params={"cookie": "claim-invalid"},
            json={**valid, "submitted_claims": []},
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/claims/draft",
            params={"cookie": "claim-invalid"},
            json={**valid, "formData": {"insured-name": "Ada", "evaluator_flag": True}},
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/claims/draft",
            params={"cookie": "claim-invalid"},
            json={**valid, "developer_tools_open": True},
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/claims/draft",
            params={"cookie": "claim-invalid"},
            json={**valid, "currentStep": 4},
        ).status_code
        == 422
    )


def test_submit_claim_is_atomic_and_visible_through_control_plane() -> None:
    cookie = "claim-submit"
    client.put(
        "/api/claims/draft",
        params={"cookie": cookie},
        json={"formData": {"insured-name": "Ada"}, "uploadedFiles": [], "currentStep": 3},
    )
    response = client.post(
        "/api/claims",
        params={"cookie": cookie},
        json={"formData": {"insured-name": "Ada"}, "uploadedFiles": []},
    )
    assert response.status_code == 201
    claim = response.json()["claim"]
    assert claim["id"].startswith("claim-")

    state = control_state(cookie)
    assert state["data"]["current_claim"] is None
    assert state["data"]["submitted_claims"][-1] == claim


def test_invalid_submission_does_not_replace_collections() -> None:
    response = client.post(
        "/api/claims",
        params={"cookie": "claim-invalid-submit"},
        json={"formData": {}, "uploadedFiles": [], "submitted_claims": [{"id": "forged"}]},
    )
    assert response.status_code == 422
    assert control_state("claim-invalid-submit")["data"]["submitted_claims"] == []


def test_control_plane_contract_and_openapi_visibility() -> None:
    cookie = "claim-control"
    put = client.put(
        "/api/state",
        params={"cookie": cookie},
        json={"data": {"nested": {"left": 1}}, "note": "put"},
    )
    assert put.status_code == 200
    patch = client.patch(
        "/api/state",
        params={"cookie": cookie},
        json={"data": {"nested": {"right": 2}}, "note": "patch"},
    )
    assert patch.status_code == 200
    assert patch.json()["state"]["data"]["nested"] == {"left": 1, "right": 2}
    assert client.delete("/api/state", params={"cookie": cookie}).status_code == 200
    assert "/api/state" not in client.get("/api/openapi.json").json()["paths"]
    assert client.get("/state-doc").status_code == 404
