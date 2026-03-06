const BACKEND_URL = "https://audio-transcription-gw7g.onrender.com/transcribe";

async function transcribe() {
  const fileInput = document.getElementById("audioFile");
  const btn = document.getElementById("transcribeBtn");
  const status = document.getElementById("status");
  const resultBox = document.getElementById("resultBox");
  const resultText = document.getElementById("resultText");

  if (!fileInput.files.length) {
    showStatus("Por favor selecciona un archivo de audio.", "error");
    return;
  }

  const file = fileInput.files[0];

  // Obtener duración del audio
  const audioDuration = await getAudioDuration(file);

  const formData = new FormData();
  formData.append("file", file);

  btn.disabled = true;
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
    const response = await fetch(BACKEND_URL, {
      method: "POST",
      body: formData,
    });

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
          resultText.textContent = data.text;
          resultBox.classList.remove("hidden");
        }
      }
    }
  } catch (err) {
    showStatus("Error: " + err.message, "error");
  } finally {
    clearInterval(timer);
    btn.disabled = false;
  }
}

function saveText() {
  const text = document.getElementById("resultText").textContent;
  const fileName = document.getElementById("infoFile").textContent.replace("Archivo: ", "");
  const saveName = fileName.replace(/\.[^.]+$/, "") + "_transcripcion.txt";

  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = saveName;
  a.click();
  URL.revokeObjectURL(url);

  resetApp();
}

function resetApp() {
  document.getElementById("audioFile").value = "";
  document.getElementById("resultBox").classList.add("hidden");
  document.getElementById("status").classList.add("hidden");
  document.getElementById("resultText").textContent = "";
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
