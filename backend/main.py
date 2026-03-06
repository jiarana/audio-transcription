import os
import math
import json
import logging
import tempfile
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from openai import OpenAI, APIError, APITimeoutError
from dotenv import load_dotenv
from pydantic import BaseModel
from pydub import AudioSegment

load_dotenv()

# --- Configuration ---

logger = logging.getLogger("transcription")
logging.basicConfig(level=logging.INFO)

# FFmpeg path (optional, falls back to system PATH)
ffmpeg_path = os.getenv("FFMPEG_PATH")
if ffmpeg_path:
    os.environ["PATH"] += os.pathsep + ffmpeg_path

# JWT secret — required, no fallback
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")

# OpenAI API key — validate at startup
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY environment variable is required")

client = OpenAI(api_key=OPENAI_API_KEY, timeout=120.0)

# Users — loaded from env: USERS=admin:$2b$12$hash,user2:$2b$12$hash
USERS: dict[str, str] = {}
users_env = os.getenv("USERS", "")
if users_env:
    for entry in users_env.split(","):
        entry = entry.strip()
        if ":" not in entry:
            continue
        username, password_hash = entry.split(":", 1)
        USERS[username.strip()] = password_hash.strip()

if not USERS:
    logger.warning("No users configured. Set USERS env var (format: user1:bcrypt_hash,user2:bcrypt_hash)")

# CORS
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8000,http://localhost:3000"
).split(",")

# File upload limits
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "100"))
ALLOWED_EXTENSIONS = {
    "mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm", "ogg", "flac", "aac",
    "wma", "amr", "opus", "mov", "avi", "mkv", "3gp",
}

CHUNK_MB = 24

# --- App setup ---

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS],
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()


# --- Models ---

class LoginRequest(BaseModel):
    username: str
    password: str


# --- Routes ---

@app.get("/")
async def root():
    return RedirectResponse(url="/app")


# Serve frontend
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/app", StaticFiles(directory=frontend_path, html=True), name="frontend")


# --- Auth ---

@app.post("/login")
async def login(data: LoginRequest):
    stored_hash = USERS.get(data.username)
    if not stored_hash or not bcrypt.checkpw(
        data.password.encode("utf-8"), stored_hash.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    token = jwt.encode(
        {"sub": data.username, "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
        JWT_SECRET,
        algorithm="HS256",
    )
    return {"token": token}


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesión expirada, vuelve a entrar")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


# --- Utils ---

def sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# --- Transcription ---

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...), _=Depends(verify_token)):
    # Validate extension
    ext = os.path.splitext(file.filename or "")[1].lower().lstrip(".") or "mp3"
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado. Formatos permitidos: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Read and validate size
    audio_bytes = await file.read()
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Archivo demasiado grande. Máximo: {MAX_FILE_SIZE_MB}MB",
        )

    async def generate():
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            audio = AudioSegment.from_file(tmp_path)
            duration_ms = len(audio)

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_file:
                audio.export(mp3_file.name, format="mp3")
                mp3_path = mp3_file.name

            with open(mp3_path, "rb") as f:
                mp3_bytes = f.read()
            os.unlink(mp3_path)

            chunk_bytes_limit = CHUNK_MB * 1024 * 1024
            if len(mp3_bytes) <= chunk_bytes_limit:
                text = _transcribe_bytes(mp3_bytes, "audio.mp3", "audio/mpeg")
                yield sse({"done": True, "text": text})
                return

            bytes_per_ms = len(mp3_bytes) / duration_ms
            chunk_ms = int(chunk_bytes_limit / bytes_per_ms)
            num_chunks = math.ceil(duration_ms / chunk_ms)

            transcriptions = []
            for i in range(num_chunks):
                yield sse({"chunk": i + 1, "total": num_chunks})

                start = i * chunk_ms
                end = min((i + 1) * chunk_ms, duration_ms)
                chunk = audio[start:end]

                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as chunk_file:
                    chunk.export(chunk_file.name, format="mp3")
                    chunk_path = chunk_file.name

                try:
                    with open(chunk_path, "rb") as f:
                        chunk_data = f.read()
                    text = _transcribe_bytes(chunk_data, f"chunk_{i}.mp3", "audio/mpeg")
                    transcriptions.append(text)
                except HTTPException:
                    yield sse({"error": "Error al transcribir fragmento de audio"})
                    return
                finally:
                    os.unlink(chunk_path)

            yield sse({"done": True, "text": " ".join(transcriptions)})

        except (APIError, APITimeoutError) as e:
            logger.error("OpenAI API error during transcription: %s", e)
            yield sse({"error": "Error en el servicio de transcripción. Intenta de nuevo."})
        except Exception as e:
            logger.error("Unexpected error during transcription: %s", e)
            yield sse({"error": "Error inesperado al procesar el audio."})
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    return StreamingResponse(generate(), media_type="text/event-stream")


def _transcribe_bytes(data: bytes, filename: str, content_type: str) -> str:
    try:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=(filename, data, content_type),
        )
        return result.text
    except (APIError, APITimeoutError) as e:
        logger.error("OpenAI transcription error: %s", e)
        raise HTTPException(status_code=502, detail="Error en el servicio de transcripción")
    except Exception as e:
        logger.error("Unexpected transcription error: %s", e)
        raise HTTPException(status_code=500, detail="Error al procesar la transcripción")
