const mapConfig = window.PETRA_MAP_CONFIG;
let latestTelemetry = null;
//conexion websoket
const socket = io();

socket.on("connect", () => setConnStatus(true));
socket.on("disconnect", () => setConnStatus(false));
socket.on("telemetry", (data) => {
  latestTelemetry = data;
  renderTelemetry(data);
  drawMap();
});
socket.on("alerts", (alerts) => alerts.forEach(showToast));

function setConnStatus(online) {
  const dot = document.getElementById("conn-dot");
  const label = document.getElementById("conn-label");
  dot.classList.toggle("online", online);
  dot.classList.toggle("offline", !online);
  label.textContent = online ? "Conectado" : "Sin conexión";
}

// menu
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebar-toggle");
sidebarToggle.addEventListener("click", () => {
  const collapsed = sidebar.classList.toggle("collapsed");
  sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
});

document.querySelectorAll(".stat-head").forEach((head) => {
  head.addEventListener("click", () => {
    head.closest(".stat-block").classList.toggle("closed");
  });
});

// estadisticas
function renderTelemetry(data) {
  // bateria
  const battLevel = data.battery.level;
  document.getElementById("battery-level").textContent =
    battLevel != null ? `${battLevel.toFixed(1)}%` : "--%";
  const fill = document.getElementById("battery-fill");
  fill.style.width = `${battLevel ?? 0}%`;
  fill.style.background =
    battLevel <= 20 ? "var(--danger)" : battLevel <= 40 ? "var(--warn)" : "var(--accent)";
  document.getElementById("battery-charging").hidden = !data.battery.charging;

  // camara
  const camPill = document.getElementById("camera-status");
  const camStatus = data.camera.status;
  camPill.textContent =
    camStatus === "ok" ? "Operativa" : camStatus === "error" ? "No enciende" : "Desconocido";
  camPill.className = "status-pill " + (camStatus === "ok" ? "ok" : camStatus === "error" ? "error" : "");

  // temperatura
  const temp = data.temperature.cpu;
  document.getElementById("temp-value").textContent = temp != null ? `${temp.toFixed(1)} °C` : "-- °C";
  const tempPill = document.getElementById("temp-status");
  const tempHigh = temp != null && temp >= 70;
  tempPill.textContent = tempHigh ? "Alta" : "Normal";
  tempPill.className = "status-pill " + (tempHigh ? "warn" : "ok");

  // autonomia
  document.getElementById("autonomy-time").textContent =
    data.autonomy.remaining_minutes != null ? `${data.autonomy.remaining_minutes} min` : "-- min";
  document.getElementById("autonomy-distance").textContent =
    data.autonomy.distance_traveled_m != null ? `${data.autonomy.distance_traveled_m} m` : "-- m";

  // estado de navegacion
  const navStatus = document.getElementById("nav-status");
  navStatus.textContent = data.goal
    ? `En camino a (${data.goal.x.toFixed(2)}, ${data.goal.y.toFixed(2)})`
    : "Robot en reposo";
}

// fotos
async function loadPhotos() {
  try {
    const res = await fetch("/api/photos");
    const photos = await res.json();
    const grid = document.getElementById("photo-grid");
    const empty = document.getElementById("photo-empty");
    if (!photos.length) {
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    grid.innerHTML = "";
    photos.forEach((url) => {
      const img = document.createElement("img");
      img.src = url;
      img.loading = "lazy";
      grid.appendChild(img);
    });
  } catch (e) {
    console.warn("No se pudieron cargar fotos", e);
  }
}
loadPhotos();

// mapa simulado, hay que enalzarlo con el slam
const canvas = document.getElementById("map-canvas");
const ctx = canvas.getContext("2d");

function resizeCanvas() {
  const wrap = canvas.parentElement;
  canvas.width = wrap.clientWidth * devicePixelRatio;
  canvas.height = wrap.clientHeight * devicePixelRatio;
  canvas.style.width = wrap.clientWidth + "px";
  canvas.style.height = wrap.clientHeight + "px";
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
}
window.addEventListener("resize", () => { resizeCanvas(); drawMap(); });

function getTransform() {
  const w = canvas.width / devicePixelRatio;
  const h = canvas.height / devicePixelRatio;
  const margin = 40;
  const scaleX = (w - margin * 2) / mapConfig.width_m;
  const scaleY = (h - margin * 2) / mapConfig.height_m;
  const scale = Math.min(scaleX, scaleY);
  const offsetX = (w - mapConfig.width_m * scale) / 2;
  const offsetY = (h - mapConfig.height_m * scale) / 2;
  return { scale, offsetX, offsetY };
}

function toPixels(xm, ym) {
  const { scale, offsetX, offsetY } = getTransform();
  return { px: offsetX + xm * scale, py: offsetY + (mapConfig.height_m - ym) * scale };
}

function toMeters(px, py) {
  const { scale, offsetX, offsetY } = getTransform();
  return { x: (px - offsetX) / scale, y: mapConfig.height_m - (py - offsetY) / scale };
}

function drawMap() {
  const w = canvas.width / devicePixelRatio;
  const h = canvas.height / devicePixelRatio;
  ctx.clearRect(0, 0, w, h);

  const { scale, offsetX, offsetY } = getTransform();
  const mapW = mapConfig.width_m * scale;
  const mapH = mapConfig.height_m * scale;

  // grid (mapa de referencia mientras no hay SLAM real)
  ctx.strokeStyle = "rgba(94, 234, 212, 0.08)";
  ctx.lineWidth = 1;
  for (let gx = 0; gx <= mapConfig.width_m; gx++) {
    const x = offsetX + gx * scale;
    ctx.beginPath();
    ctx.moveTo(x, offsetY);
    ctx.lineTo(x, offsetY + mapH);
    ctx.stroke();
  }
  for (let gy = 0; gy <= mapConfig.height_m; gy++) {
    const y = offsetY + gy * scale;
    ctx.beginPath();
    ctx.moveTo(offsetX, y);
    ctx.lineTo(offsetX + mapW, y);
    ctx.stroke();
  }

  // borde del área
  ctx.strokeStyle = "rgba(94, 234, 212, 0.35)";
  ctx.lineWidth = 1.5;
  ctx.strokeRect(offsetX, offsetY, mapW, mapH);

  // salas / destinos
  ctx.font = "12px 'Rajdhani', sans-serif";
  (mapConfig.rooms || []).forEach((room) => {
    const p1 = toPixels(room.x, room.y + room.h);
    const isCurrent = latestTelemetry && latestTelemetry.current_room === room.name;
    ctx.strokeStyle = isCurrent ? "rgba(94, 234, 212, 0.6)" : "rgba(139, 152, 165, 0.35)";
    ctx.lineWidth = isCurrent ? 2 : 1;
    ctx.strokeRect(p1.px, p1.py, room.w * scale, room.h * scale);
    ctx.fillStyle = isCurrent ? "rgba(94, 234, 212, 0.9)" : "rgba(139, 152, 165, 0.7)";
    ctx.fillText(room.name.toUpperCase(), p1.px + 8, p1.py + 18);
  });

  // meta activa (sala hacia la que navega el robot)
  if (latestTelemetry && latestTelemetry.goal) {
    const p = toPixels(latestTelemetry.goal.x, latestTelemetry.goal.y);
    ctx.fillStyle = "rgba(245, 166, 35, 0.9)";
    ctx.beginPath();
    ctx.arc(p.px, p.py, 5, 0, Math.PI * 2);
    ctx.fill();
  }

  // robot: marcador simple, sin animación
  if (latestTelemetry) {
    const pos = latestTelemetry.position;
    const p = toPixels(pos.x, pos.y);
    ctx.fillStyle = "#5EEAD4";
    ctx.beginPath();
    ctx.arc(p.px, p.py, 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "rgba(94, 234, 212, 0.4)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(p.px, p.py, 13, 0, Math.PI * 2);
    ctx.stroke();
  }
}

//  Destinos predefinidos (Aula A, Aula B, Aula C...) 
const destinationSelect = document.getElementById("destination-select");
const currentRoomNote = document.getElementById("current-room-note");
let lastKnownRoom = undefined; // para no recargar el <select> en cada telemetría si no cambió

async function loadDestinations() {
  try {
    const res = await fetch("/api/locations");
    const data = await res.json();

    currentRoomNote.textContent = `Sala actual: ${data.current_room || "en tránsito"}`;

    if (data.current_room === lastKnownRoom) return; // sin cambios, no tocar el select
    lastKnownRoom = data.current_room;

    const previousValue = destinationSelect.value;
    destinationSelect.innerHTML = '<option value="">Elegir destino…</option>';
    data.destinations.forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d.name;
      opt.textContent = d.name;
      destinationSelect.appendChild(opt);
    });
    // conserva la selección si sigue siendo válida
    if ([...destinationSelect.options].some((o) => o.value === previousValue)) {
      destinationSelect.value = previousValue;
    }
  } catch (e) {
    console.warn("No se pudieron cargar los destinos", e);
  }
}

document.getElementById("goal-send").addEventListener("click", async () => {
  const location = destinationSelect.value;
  if (!location) {
    showToast({ type: "temp_high", message: "Elige un destino primero" });
    return;
  }
  try {
    const res = await fetch("/api/navigate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ location }),
    });
    const result = await res.json();
    if (result.ok) {
      showToast({ type: "info", message: result.message || `Robot en camino a ${location}` });
    } else {
      showToast({ type: "temp_high", message: result.message || "No se pudo enviar la meta" });
    }
  } catch (e) {
    showToast({ type: "temp_high", message: "Error de red al enviar la meta" });
  }
});

loadDestinations();
setInterval(loadDestinations, 3000); // refresca la lista si el robot cambió de sala

// cambio de modo (mock / ros)
const modeSwitch = document.getElementById("mode-switch");
if (modeSwitch) {
  const btnMock = document.getElementById("btn-mock");
  const btnRos = document.getElementById("btn-ros");

  function setActiveModeButton(mode) {
    btnMock.classList.toggle("active", mode === "mock");
    btnRos.classList.toggle("active", mode === "ros");
  }
  setActiveModeButton(window.PETRA_CURRENT_MODE === "ros" ? "ros" : "mock");

  async function switchMode(mode) {
    try {
      const res = await fetch("/api/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      const result = await res.json();
      if (result.ok) {
        setActiveModeButton(result.mode);
        showToast({ type: "info", message: `Modo cambiado a ${result.mode.toUpperCase()}` });
      } else {
        showToast({ type: "temp_high", message: result.message });
      }
    } catch (e) {
      showToast({ type: "temp_high", message: "No se pudo cambiar de modo" });
    }
  }
  btnMock.addEventListener("click", () => switchMode("mock"));
  btnRos.addEventListener("click", () => switchMode("ros"));

  fetch("/api/mode").then((r) => r.json()).then((d) => setActiveModeButton(d.mode));
}

// toast
function showToast({ type, message }) {
  const stack = document.getElementById("toast-stack");
  const el = document.createElement("div");
  const cls = type === "battery_low" || type === "temp_high" ? "warn"
    : type === "camera_error" ? "error" : "";
  el.className = `toast ${cls}`;
  el.textContent = message;
  stack.appendChild(el);
  setTimeout(() => el.remove(), 6000);
}

// init
resizeCanvas();
drawMap();
