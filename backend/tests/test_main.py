import io
import json
from unittest.mock import patch, MagicMock

import jwt
import pytest


# --- Login tests ---

@pytest.mark.anyio
async def test_login_success(client):
    resp = await client.post("/login", json={"username": "testuser", "password": "testpass123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    decoded = jwt.decode(data["token"], "test-secret-for-testing-only", algorithms=["HS256"])
    assert decoded["sub"] == "testuser"


@pytest.mark.anyio
async def test_login_wrong_password(client):
    resp = await client.post("/login", json={"username": "testuser", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_login_unknown_user(client):
    resp = await client.post("/login", json={"username": "nobody", "password": "pass"})
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_login_missing_fields(client):
    resp = await client.post("/login", json={})
    assert resp.status_code == 422  # Pydantic validation error


@pytest.mark.anyio
async def test_login_invalid_body(client):
    resp = await client.post("/login", content="not json", headers={"Content-Type": "application/json"})
    assert resp.status_code == 422


# --- Token verification tests ---

@pytest.mark.anyio
async def test_transcribe_no_token(client):
    resp = await client.post("/transcribe")
    assert resp.status_code == 401  # No credentials


@pytest.mark.anyio
async def test_transcribe_invalid_token(client):
    resp = await client.post(
        "/transcribe",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_transcribe_expired_token(client):
    from datetime import datetime, timedelta, timezone

    expired_token = jwt.encode(
        {"sub": "testuser", "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
        "test-secret-for-testing-only",
        algorithm="HS256",
    )
    resp = await client.post(
        "/transcribe",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401
    assert "expirada" in resp.json()["detail"].lower()


# --- File validation tests ---

@pytest.mark.anyio
async def test_transcribe_invalid_extension(client, auth_token):
    resp = await client.post(
        "/transcribe",
        headers={"Authorization": f"Bearer {auth_token}"},
        files={"file": ("test.exe", b"fake content", "application/octet-stream")},
    )
    assert resp.status_code == 400
    assert "formato" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_transcribe_file_too_large(client, auth_token):
    # Create a file slightly over the limit (simulated with patched MAX_FILE_SIZE_MB=0)
    with patch("backend.main.MAX_FILE_SIZE_MB", 0):
        resp = await client.post(
            "/transcribe",
            headers={"Authorization": f"Bearer {auth_token}"},
            files={"file": ("test.mp3", b"some audio bytes", "audio/mpeg")},
        )
    assert resp.status_code == 400
    assert "grande" in resp.json()["detail"].lower()


# --- Transcription integration test (mocked OpenAI) ---

@pytest.mark.anyio
async def test_transcribe_success_sse(client, auth_token):
    # Mock AudioSegment since FFmpeg may not be available in test env
    mock_audio = MagicMock()
    mock_audio.__len__ = lambda self: 5000  # 5 seconds in ms
    mock_audio.export = MagicMock()

    fake_audio_bytes = b"fake audio content for testing"

    with patch("backend.main.AudioSegment.from_file", return_value=mock_audio), \
         patch("backend.main._transcribe_bytes", return_value="Hola mundo transcrito"), \
         patch("builtins.open", MagicMock(return_value=io.BytesIO(fake_audio_bytes))):
        resp = await client.post(
            "/transcribe",
            headers={"Authorization": f"Bearer {auth_token}"},
            files={"file": ("test.mp3", b"fake mp3 content", "audio/mpeg")},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    # Parse SSE events
    events = []
    for line in resp.text.strip().split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))

    assert len(events) >= 1
    last_event = events[-1]
    assert last_event.get("done") is True
    assert last_event.get("text") == "Hola mundo transcrito"
