# Transcripción de Audio

Aplicación web para transcribir archivos de audio y vídeo usando la API de OpenAI. El usuario sube un archivo desde el navegador y recibe la transcripción en texto, con soporte de múltiples idiomas y archivos de gran tamaño.

**Demo:** https://audio-transcription-gw7g.onrender.com

---

## Características

- Transcripción con el modelo `gpt-4o-transcribe` (OpenAI)
- Soporte de múltiples idiomas con auto-detección
- Archivos de hasta 100 MB — los archivos grandes se dividen automáticamente en fragmentos
- Resultado editable antes de copiar o guardar
- Descarga del resultado como `.txt`
- Diseño responsive, optimizado para móvil
- Autenticación con usuario y contraseña (JWT)

## Formatos soportados

`mp3` · `mp4` · `m4a` · `wav` · `webm` · `ogg` · `flac` · `aac` · `opus` · `wma` · `amr` · `mov` · `avi` · `mkv` · `3gp` · `mpeg`

---

## Pila tecnológica

| Capa | Tecnología |
|---|---|
| Backend | Python · FastAPI · Uvicorn |
| Transcripción | OpenAI API (`gpt-4o-transcribe`) |
| Procesado de audio | pydub · FFmpeg |
| Autenticación | JWT (PyJWT) + bcrypt |
| Frontend | HTML · CSS · JavaScript (vanilla) |
| Deploy | Render |

---

## Estructura del proyecto

```
audio-transcription/
├── backend/
│   ├── main.py              # Servidor FastAPI (API + sirviente del frontend)
│   ├── requirements.txt
│   └── tests/
│       ├── conftest.py
│       └── test_main.py     # 11 tests (pytest)
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── docs/                    # Notas de sesiones de desarrollo
└── runtime.txt              # Versión de Python para Render
```

---

## Instalación y desarrollo local

### Requisitos previos

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/download.html) instalado y disponible en `PATH`
- Cuenta de OpenAI con acceso a la API

### 1. Clonar el repositorio

```bash
git clone https://github.com/jiarana/audio-transcription.git
cd audio-transcription
```

### 2. Instalar dependencias

```bash
cd backend
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Crear el archivo `backend/.env`:

```env
OPENAI_API_KEY=sk-...
JWT_SECRET=una-clave-secreta-larga-y-aleatoria
USERS=admin:$2b$12$hash_bcrypt_de_la_contraseña
```

Para generar el hash de una contraseña:

```python
import bcrypt
print(bcrypt.hashpw(b"tu_contraseña", bcrypt.gensalt()).decode())
```

Variables opcionales:

```env
MAX_FILE_SIZE_MB=100
ALLOWED_ORIGINS=http://localhost:8000
FFMPEG_PATH=/ruta/a/ffmpeg/bin   # Solo si FFmpeg no está en PATH
```

### 4. Arrancar el servidor

```bash
cd backend
uvicorn main:app --reload
```

Abrir en el navegador: http://localhost:8000/app

---

## Tests

```bash
cd audio-transcription
python -m pytest backend/tests/ -v
```

11 tests cubren: login, verificación de token, validación de archivos y flujo SSE de transcripción.

---

## Deploy en Render

El proyecto está configurado para desplegarse en [Render](https://render.com) como un **Web Service** de Python.

Variables de entorno requeridas en el dashboard de Render:

| Variable | Descripción |
|---|---|
| `OPENAI_API_KEY` | Clave de la API de OpenAI |
| `JWT_SECRET` | Clave secreta para firmar tokens JWT |
| `USERS` | Usuarios en formato `user1:bcrypt_hash,user2:bcrypt_hash` |
| `ALLOWED_ORIGINS` | URL del servicio en Render (para CORS) |

> **Nota:** Los valores de `USERS` contienen `$` en los hashes bcrypt. Verificar en el dashboard de Render que el valor no se haya truncado por interpolación de shell.

Comando de inicio: `uvicorn main:app --host 0.0.0.0 --port $PORT`

---

## Licencia

Uso privado.
