import os

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


def _settings() -> Settings:
    return Settings(
        groq_api_key="test-groq-key-not-a-real-secret-000000",
        database_url="postgresql://test:test@127.0.0.1:55432/test",
        frontend_origins=["https://rag-playground-alpha.vercel.app"],
        frontend_origin_regex=(
            r"^https://rag-playground-[a-z0-9-]+-yashs-projects-98b2c247\.vercel\.app$"
        ),
        public_api_url="https://api.example.test",
        allowed_hosts=["testserver"],
        ip_hash_salt="unit-test-ip-hash-salt-000000",
        verify_fallback_token=os.environ["VERIFY_FALLBACK_TOKEN"],
    )


def test_vercel_project_preview_origin_is_allowed(pipeline) -> None:
    application = create_app(_settings(), pipeline)
    client = TestClient(application)
    origin = "https://rag-playground-build123-yashs-projects-98b2c247.vercel.app"

    response = client.options(
        "/v1/config",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_unrelated_vercel_origin_is_rejected(pipeline) -> None:
    application = create_app(_settings(), pipeline)
    client = TestClient(application)

    response = client.options(
        "/v1/config",
        headers={
            "Origin": "https://rag-playground-build123-someone-else.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
