import os
import bcrypt
import pytest

# Set required env vars BEFORE importing the app
_password = "testpass123"
_hash = bcrypt.hashpw(_password.encode(), bcrypt.gensalt()).decode()

os.environ.setdefault("JWT_SECRET", "test-secret-for-testing-only")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key")
os.environ.setdefault("USERS", f"testuser:{_hash}")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from backend.main import app  # noqa: E402


@pytest.fixture
def test_password():
    return _password


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_token(client):
    resp = await client.post("/login", json={"username": "testuser", "password": _password})
    assert resp.status_code == 200
    return resp.json()["token"]
