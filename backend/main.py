import os
import math
import json
import tempfile

os.environ["PATH"] += r";C:\Users\jiarana\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin"

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from dotenv import load_dotenv
from pydub import AudioSegment

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CHUNK_MB = 24


def sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="API key no configurada en .env")

    audio_bytes = await file.read()
    ext = os.path.splitext(file.filename)[1].lower().lstrip(".") or "mp3"

    async def generate():
        # Archivo pequeño: transcribir directo
        if len(audio_bytes) <= CHUNK_MB * 1024 * 1024:
            try:
                text = _transcribe_bytes(audio_bytes, file.filename, file.content_type)
                yield sse({"done": True, "text": text})
            except HTTPException as e:
                yield sse({"error": e.detail})
            return

        # Archivo grande: fragmentar
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            audio = AudioSegment.from_file(tmp_path)
            duration_ms = len(audio)
            bytes_per_ms = len(audio_bytes) / duration_ms
            chunk_ms = int((CHUNK_MB * 1024 * 1024) / bytes_per_ms)
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
                except HTTPException as e:
                    yield sse({"error": e.detail})
                    return
                finally:
                    os.unlink(chunk_path)

            yield sse({"done": True, "text": " ".join(transcriptions)})

        except Exception as e:
            yield sse({"error": str(e)})
        finally:
            os.unlink(tmp_path)

    return StreamingResponse(generate(), media_type="text/event-stream")


def _transcribe_bytes(data: bytes, filename: str, content_type: str) -> str:
    try:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=(filename, data, content_type),
        )
        return result.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
