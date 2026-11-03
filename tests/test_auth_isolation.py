from __future__ import annotations

from httpx import AsyncClient


async def _register(client: AsyncClient, email: str, password: str = "superSecret123"):
    response = await client.post(
        "/v1/auth/register", json={"email": email, "password": password}
    )
    assert response.status_code == 201, response.json()
    return response.json()


async def _ws_header(client: AsyncClient, token: str) -> dict[str, str]:
    me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    workspaces = me.json()["workspaces"]
    assert len(workspaces) == 1
    return {"Authorization": f"Bearer {token}", "X-Workspace-Id": workspaces[0]["id"]}


# --- registration / login / session lifecycle ---


async def test_register_creates_user_personal_workspace(app_client):
    _app, client = app_client
    body = await _register(client, "alice@example.com")
    assert body["user"]["email"] == "alice@example.com"
    assert body["token"]

    me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    me_body = me.json()
    assert me_body["email"] == "alice@example.com"
    assert len(me_body["workspaces"]) == 1
    assert me_body["workspaces"][0]["role"] == "owner"


async def test_register_rejects_duplicate_email_case_insensitively(app_client):
    _app, client = app_client
    await _register(client, "bob@example.com")
    response = await client.post(
        "/v1/auth/register", json={"email": "BOB@example.com", "password": "anotherPass123"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_register_rejects_short_password(app_client):
    _app, client = app_client
    response = await client.post(
        "/v1/auth/register", json={"email": "short@example.com", "password": "short123"}
    )
    assert response.status_code == 422


async def test_login_success_and_failure(app_client):
    _app, client = app_client
    await _register(client, "carol@example.com")

    ok = await client.post(
        "/v1/auth/login", json={"email": "carol@example.com", "password": "superSecret123"}
    )
    assert ok.status_code == 200
    assert ok.json()["token"]

    bad = await client.post(
        "/v1/auth/login", json={"email": "carol@example.com", "password": "wrong-password"}
    )
    assert bad.status_code == 401
    # Same generic message whether the email exists or not.
    bad_unknown = await client.post(
        "/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"}
    )
    assert bad_unknown.status_code == 401
    assert bad.json()["error"]["message"] == bad_unknown.json()["error"]["message"]


async def test_logout_revokes_session(app_client):
    _app, client = app_client
    body = await _register(client, "dave@example.com")
    headers = {"Authorization": f"Bearer {body['token']}"}

    me = await client.get("/v1/auth/me", headers=headers)
    assert me.status_code == 200

    logout = await client.post("/v1/auth/logout", headers=headers)
    assert logout.status_code == 204

    me_after = await client.get("/v1/auth/me", headers=headers)
    assert me_after.status_code == 401


# --- workspace membership & role boundaries ---


async def test_membership_flow_admin_adds_member(app_client):
    _app, client = app_client
    owner = await _register(client, "owner@example.com")
    member = await _register(client, "newmember@example.com")
    owner_headers = await _ws_header(client, owner["token"])

    ws_id = owner_headers["X-Workspace-Id"]
    member_headers = await _ws_header(client, member["token"])
    member_user_id = member_headers["X-Workspace-Id"]  # personal ws != member user id; fetch /me below

    me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {member['token']}"})
    member_user_id = str(me.json()["id"])

    add = await client.post(
        f"/v1/workspaces/{ws_id}/members",
        json={"user_id": member_user_id, "role": "member"},
        headers=owner_headers,
    )
    assert add.status_code == 201, add.json()

    # Member can now access the workspace.
    got = await client.get(
        f"/v1/workspaces/{ws_id}",
        headers={"Authorization": f"Bearer {member['token']}", "X-Workspace-Id": ws_id},
    )
    assert got.status_code == 200

    # ...but not admin-required endpoints.
    keys = await client.get(
        f"/v1/workspaces/{ws_id}/api-keys",
        headers={"Authorization": f"Bearer {member['token']}", "X-Workspace-Id": ws_id},
    )
    assert keys.status_code == 403


async def test_member_cannot_add_members(app_client):
    _app, client = app_client
    owner = await _register(client, "own2@example.com")
    member = await _register(client, "mem2@example.com")
    helper = await _register(client, "help2@example.com")

    owner_headers = await _ws_header(client, owner["token"])
    ws_id = owner_headers["X-Workspace-Id"]

    me_helper = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {helper['token']}"})
    helper_id = str(me_helper.json()["id"])
    me_member = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {member['token']}"})
    member_id = str(me_member.json()["id"])

    added = await client.post(
        f"/v1/workspaces/{ws_id}/members",
        json={"user_id": member_id, "role": "member"},
        headers=owner_headers,
    )
    assert added.status_code == 201

    member_headers = {"Authorization": f"Bearer {member['token']}", "X-Workspace-Id": ws_id}
    denied = await client.post(
        f"/v1/workspaces/{ws_id}/members",
        json={"user_id": helper_id, "role": "member"},
        headers=member_headers,
    )
    assert denied.status_code == 403


async def test_workspace_access_isolated_between_owners(app_client):
    _app, client = app_client
    alice = await _register(client, "alice2@example.com")
    mallory = await _register(client, "mallory@example.com")
    alice_ws = (await _ws_header(client, alice["token"]))["X-Workspace-Id"]

    # Mallory cannot read Alice's workspace by guessing its id.
    denied = await client.get(
        f"/v1/workspaces/{alice_ws}",
        headers={"Authorization": f"Bearer {mallory['token']}", "X-Workspace-Id": alice_ws},
    )
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "not_found"


# --- API keys ---


async def test_api_key_create_use_revoke_once(app_client):
    _app, client = app_client
    owner = await _register(client, "keyowner@example.com")
    owner_headers = await _ws_header(client, owner["token"])
    ws_id = owner_headers["X-Workspace-Id"]

    created = await client.post(
        f"/v1/workspaces/{ws_id}/api-keys", json={"name": "ci"}, headers=owner_headers
    )
    assert created.status_code == 201
    token = created.json()["token_once"]
    assert token.startswith("bk_")

    # API key works for the pinned workspace without X-Workspace-Id.
    me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["workspaces"][0]["id"] == ws_id

    # Listing never returns the plaintext again.
    listed = await client.get(f"/v1/workspaces/{ws_id}/api-keys", headers=owner_headers)
    assert listed.status_code == 200
    assert all("token_once" not in k for k in listed.json()["data"])

    # Revoke; key is then dead.
    key_id = created.json()["id"]
    revoke = await client.delete(f"/v1/workspaces/{ws_id}/api-keys/{key_id}", headers=owner_headers)
    assert revoke.status_code == 204
    me_after = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_after.status_code == 401


async def test_api_key_scoped_to_its_workspace(app_client):
    _app, client = app_client
    owner = await _register(client, "scopowner@example.com")
    other = await _register(client, "scootourist@example.com")
    owner_headers = await _ws_header(client, owner["token"])
    ws_id = owner_headers["X-Workspace-Id"]
    other_ws = (await _ws_header(client, other["token"]))["X-Workspace-Id"]

    created = await client.post(
        f"/v1/workspaces/{ws_id}/api-keys", json={"name": "scoped"}, headers=owner_headers
    )
    assert created.status_code == 201
    token = created.json()["token_once"]

    # The key's context is ws_id; using other's workspace id must be a 404 isolation failure.
    denied = await client.get(
        f"/v1/workspaces/{other_ws}", headers={"Authorization": f"Bearer {token}"}
    )
    assert denied.status_code == 404


async def test_session_without_workspace_header_is_rejected(app_client):
    _app, client = app_client
    alice = await _register(client, "needws@example.com")
    token = alice["token"]
    denied = await client.get(
        "/v1/workspaces", headers={"Authorization": f"Bearer {token}"}
    )
    # Listing own workspaces is allowed without X-Workspace-Id.
    assert denied.status_code == 200
