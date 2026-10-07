def register(client, email="ana@example.com", password="password123"):
    return client.post("/auth/register", json={"email": email, "password": password})


def login(client, email="ana@example.com", password="password123"):
    return client.post("/auth/login", data={"username": email, "password": password})


def test_register_then_login_then_me(client):
    assert register(client).status_code == 201

    response = login(client)
    assert response.status_code == 200
    token = response.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "ana@example.com"
    assert me.json()["is_admin"] is False


def test_email_is_case_insensitive(client):
    register(client, email="Ana@Example.com")

    assert register(client, email="ana@example.com").status_code == 409
    assert login(client, email="ANA@example.com").status_code == 200


def test_wrong_password_is_rejected(client):
    register(client)

    assert login(client, password="not-the-password").status_code == 401


def test_short_password_is_rejected(client):
    assert register(client, password="short").status_code == 422


def test_password_is_not_stored_in_plain_text(client):
    from app.core.db import SessionLocal
    from app.models import User

    register(client)
    with SessionLocal() as db:
        user = db.query(User).one()
    assert user.hashed_password != "password123"


def test_me_requires_a_valid_token(client):
    assert client.get("/auth/me").status_code == 401
    bad = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/auth/me", headers=bad).status_code == 401
