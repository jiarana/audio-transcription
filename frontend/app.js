const BACKEND_URL = window.location.protocol === "file:"
  ? "http://localhost:8000"
  : window.location.origin;

const MAX_FILE_SIZE_MB = 100;

// --- Sesión ---

function getToken() {
  return sessionStorage.getItem("token");
}

function showApp() {
  document.getElementById("loginBox").classList.add("hidden");
  document.getElementById("appBox").classList.remove("hidden");
}

function showLogin() {
  document.getElementById("appBox").classList.add("hidden");
  document.getElementById("loginBox").classList.remove("hidden");
}

// Verificar si ya hay sesión activa al cargar
window.addEventListener("load", () => {
  if (getToken()) showApp();
});

// --- Login ---

async function doLogin() {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;

  if (!username || !password) {
    showLoginStatus("Introduce usuario y contraseña.", "error");
    return;
  }

  try {
    const response = await fetch(`${BACKEND_URL}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      showLoginStatus(data.detail || "Error al iniciar sesión.", "error");
      return;
    }

    sessionStorage.setItem("token", data.token);
    document.getElementById("username").value = "";
    document.getElementById("password").value = "";
    document.getElementById("loginStatus").classList.add("hidden");
    showApp();
  } catch {
    showLoginStatus("No se pudo conectar con el servidor.", "error");
  }
}

function logout() {
  sessionStorage.removeItem("token");
  resetApp();
  showLogin();
}

function showLoginStatus(message, type) {
  const el = document.getElementById("loginStatus");
  el.textContent = message;
  el.className = "status " + type;
}

function updateFileName() {
  const fileInput = document.getElementById("audioFile");
  const label = document.getElementById("fileName");
  label.textContent = fileInput.files.length ? fileInput.files[0].name : "Ningún archivo seleccionado";
}

// --- Transcripción ---

function setTranscribing(active) {
  document.getElementById("transcribeBtn").disabled = active;
  document.getElementById("selectFileBtn").disabled = active;
}

async function transcribe() {
  const fileInput = document.getElementById("audioFile");
  const status = document.getElementById("status");
  const resultBox = document.getElementById("resultBox");
  const resultText = document.getElementById("resultText");

  if (!fileInput.files.length) {
    showStatus("Por favor selecciona un archivo de audio o video.", "error");
    return;
  }

  const file = fileInput.files[0];

  // Validate file size on client
  const fileSizeMB = file.size / (1024 * 1024);
  if (fileSizeMB > MAX_FILE_SIZE_MB) {
    showStatus(`El archivo es demasiado grande (${fileSizeMB.toFixed(1)}MB). Máximo: ${MAX_FILE_SIZE_MB}MB.`, "error");
    return;
  }

  const audioDuration = await getAudioDuration(file);
  const formData = new FormData();
  formData.append("file", file);
  const language = document.getElementById("langSelect").value;
  if (language) formData.append("language", language);

  setTranscribing(true);
  resultBox.classList.add("hidden");

  const startTime = Date.now();
  let seconds = 0;
  let chunkInfo = "";
  const timer = setInterval(() => {
    seconds++;
    showStatus(`Transcribiendo${chunkInfo}... ${seconds}s`, "loading");
  }, 1000);
  showStatus("Transcribiendo... 0s", "loading");

  try {
    const response = await fetch(`${BACKEND_URL}/transcribe`, {
      method: "POST",
      headers: { Authorization: `Bearer ${getToken()}` },
      body: formData,
    });

    if (response.status === 401) {
      sessionStorage.removeItem("token");
      showLoginStatus("Tu sesión ha expirado. Por favor, inicia sesión de nuevo.", "error");
      showLogin();
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = JSON.parse(line.slice(6));

        if (data.error) throw new Error(data.error);

        if (data.chunk) {
          chunkInfo = ` fragmento ${data.chunk} de ${data.total}`;
        }

        if (data.done) {
          clearInterval(timer);
          const elapsed = Math.round((Date.now() - startTime) / 1000);

          document.getElementById("infoFile").textContent = `Archivo: ${file.name}`;
          document.getElementById("infoDuration").textContent = audioDuration
            ? `Duración: ${formatDuration(audioDuration)}`
            : "";
          document.getElementById("infoTime").textContent = `Tiempo de transcripción: ${elapsed}s`;

          status.classList.add("hidden");
          resultText.value = data.text;
          resultBox.classList.remove("hidden");
        }
      }
    }
  } catch (err) {
    showStatus("Error: " + err.message, "error");
  } finally {
    clearInterval(timer);
    setTranscribing(false);
  }
}

function copyText() {
  const text = document.getElementById("resultText").value;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById("copyBtn");
    btn.textContent = "¡Copiado!";
    btn.classList.add("btn-copied");
    setTimeout(() => {
      btn.textContent = "Copiar";
      btn.classList.remove("btn-copied");
    }, 2000);
  });
}

function saveText() {
  const text = document.getElementById("resultText").value;
  const fileName = document.getElementById("infoFile").textContent.replace("Archivo: ", "");
  const saveName = fileName.replace(/\.[^.]+$/, "") + "_transcripcion.txt";

  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = saveName;
  a.click();
  URL.revokeObjectURL(url);
}

function resetApp() {
  document.getElementById("audioFile").value = "";
  document.getElementById("fileName").textContent = "Ningún archivo seleccionado";
  document.getElementById("langSelect").value = "";
  document.getElementById("resultBox").classList.add("hidden");
  document.getElementById("status").classList.add("hidden");
  document.getElementById("resultText").value = "";
}

function getAudioDuration(file) {
  return new Promise((resolve) => {
    const audio = document.createElement("audio");
    audio.src = URL.createObjectURL(file);
    audio.onloadedmetadata = () => {
      URL.revokeObjectURL(audio.src);
      resolve(audio.duration);
    };
    audio.onerror = () => resolve(null);
  });
}

function formatDuration(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function showStatus(message, type) {
  const status = document.getElementById("status");
  status.textContent = message;
  status.className = "status " + type;
}
