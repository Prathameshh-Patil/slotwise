from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_plain_postgres_urls_use_the_psycopg_driver():
    from app.core.config import Settings

    for given in ("postgres://u:p@h:5432/d", "postgresql://u:p@h:5432/d"):
        assert Settings(database_url=given).database_url == "postgresql+psycopg://u:p@h:5432/d"
    kept = "postgresql+psycopg://u:p@h:5432/d"
    assert Settings(database_url=kept).database_url == kept
