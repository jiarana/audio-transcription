# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

Web app de transcripcion de audio y video con la API de OpenAI (modelo `gpt-4o-transcribe`). El usuario inicia sesion, sube un archivo desde el navegador y recibe la transcripcion (editable, copiable y descargable como `.txt`).

- Produccion: https://audio-transcription-gw7g.onrender.com (Render, autodeploy al hacer push a `main`)
- Repo: https://github.com/jiarana/audio-transcription
- `README.md` es la documentacion de referencia para usuarios; `docs/` guarda notas de sesiones de desarrollo.

## Antes de empezar

Se trabaja desde varias maquinas/sesiones. Ejecutar siempre `git fetch` y comparar con `origin/main` antes de resumir el estado del proyecto, commitear o hacer push.

## Build & Development Commands

```bash
# Instalar dependencias (incluye pytest)
cd backend && pip install -r requirements.txt

# Iniciar el servidor (desde /backend); el frontend se sirve en http://localhost:8000/app
uvicorn main:app --reload

# Tests (desde la raiz del repo; la llamada a OpenAI esta mockeada)
python -m pytest backend/tests/ -v
```

## Architecture

- **Backend:** Python 3.12 + FastAPI, todo en `backend/main.py`.
  - `POST /login` — valida usuario/contrasena (bcrypt) y devuelve un JWT (HS256, 8 h).
  - `POST /transcribe` — requiere Bearer token. Recibe `file` y `language` opcional. Responde por SSE (`text/event-stream`) con eventos `{chunk, total}`, `{done, text}` o `{error}`.
  - `/app` sirve el frontend como estatico; `/` redirige a `/app`.
- **Procesado de audio:** el audio siempre se convierte a MP3 con pydub (requiere FFmpeg) antes de transcribir; si supera 24 MB se divide en fragmentos por duracion.
- **Frontend:** HTML + CSS + JS vanilla sin dependencias (`frontend/index.html`, `style.css`, `app.js`). Usa URLs relativas.

```
Audio-Transcription/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── .env.example      # Plantilla de variables de entorno
│   ├── .env              # No subir a git
│   └── tests/            # pytest (conftest.py, test_main.py)
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── docs/                 # Notas de sesiones
├── README.md
└── runtime.txt           # Python 3.12 para Render
```

## Variables de Entorno

Copiar `backend/.env.example` a `backend/.env`. El servidor no arranca si faltan las requeridas.

| Variable | Requerida | Descripcion |
|---|---|---|
| `OPENAI_API_KEY` | si | API key de OpenAI |
| `JWT_SECRET` | si | Clave para firmar los JWT |
| `USERS` | si | `user1:bcrypt_hash,user2:bcrypt_hash` |
| `ALLOWED_ORIGINS` | no | CORS, separado por comas (defecto: localhost:8000 y :3000) |
| `MAX_FILE_SIZE_MB` | no | Tamano maximo de subida (defecto: 100) |
| `FFMPEG_PATH` | no | Carpeta de FFmpeg si no esta en el PATH |

Generar un hash: `python -c "import bcrypt; print(bcrypt.hashpw(b'pass', bcrypt.gensalt()).decode())"`

## Code Style

Python simple y directo. Sin clases innecesarias. Frontend en JS vanilla sin dependencias. Mensajes al usuario en espanol.
