"""
Shared fixtures for all API tests.

Requires environment variables:
  SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY
  TEST_EMAIL, TEST_PASSWORD  (defaults to test@test.com / from CLAUDE.md)

Services must be running:
  Backend:  http://localhost:8000
  (Supabase: cloud, accessed via REST)
"""
import os
import pytest
import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../backend/.env"))

API_BASE = os.getenv("TEST_API_BASE", "http://localhost:8000")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
TEST_EMAIL = os.getenv("TEST_EMAIL", "test@test.com")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "!*-3-3?3uZ?b$v&")


def get_jwt(email: str, password: str) -> str:
    """Authenticate with Supabase and return a JWT access token."""
    resp = httpx.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=15,
    )
    assert resp.status_code == 200, f"Auth failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def jwt_token():
    """Session-scoped JWT — authenticates once per test run."""
    return get_jwt(TEST_EMAIL, TEST_PASSWORD)


@pytest.fixture(scope="session")
def auth_headers(jwt_token):
    return {"Authorization": f"Bearer {jwt_token}"}


@pytest.fixture(scope="session")
def client():
    """Shared httpx client."""
    with httpx.Client(base_url=API_BASE, timeout=30) as c:
        yield c


@pytest.fixture()
def authed_client(client, auth_headers):
    """Client with auth headers pre-set."""
    client.headers.update(auth_headers)
    yield client
    # Reset headers after each test
    client.headers.pop("Authorization", None)
