# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

Web app de transcripcion de audio usando OpenAI Whisper. El usuario sube un archivo de audio desde el navegador y recibe la transcripcion en texto.

## Build & Development Commands

```bash
# Instalar dependencias del backend
cd backend && pip install -r requirements.txt

# Iniciar el servidor backend (desde /backend)
uvicorn main:app --reload

# Frontend: abrir directamente en el navegador
frontend/index.html
```

## Architecture

- **Frontend:** HTML + CSS + JS vanilla. Sin frameworks. Archivo unico `index.html`.
- **Backend:** Python + FastAPI. Un endpoint `POST /transcribe` que recibe el audio y llama a Whisper.
- **Transcripcion:** OpenAI Whisper API via `openai` Python SDK (modelo `whisper-1`).

```
test01/
├── backend/
│   ├── main.py           # Servidor FastAPI
│   ├── requirements.txt
│   └── .env              # OPENAI_API_KEY (no subir a git)
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

## Variables de Entorno

Editar `backend/.env`:
```
OPENAI_API_KEY=sk-tu-api-key-aqui
```

## Code Style

Python simple y directo. Sin clases innecesarias. Frontend en JS vanilla sin dependencias.
