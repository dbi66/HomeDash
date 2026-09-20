const state = { home: null, rooms: [], view: "home" };

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[char]));

const metric = (label, value, detail) => `<article class="card"><div class="metric-label">${esc(label)}</div><div class="metric-value">${esc(value)}</div><div class="metric-detail">${esc(detail)}</div></article>`;

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function setView(view) {
  state.view = view;
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  render();
}

function renderHeader() {
  document.querySelector("#freshness").textContent = `Homematic: ${state.home.latest_homematic ?? "nicht verfügbar"} · Viessmann: ${state.home.latest_viessmann ?? "nicht verfügbar"}`;
}

function renderHome() {
  const data = state.home;
  document.querySelector("#page-title").textContent = "Dein Zuhause auf einen Blick";
  document.querySelector("#metrics").innerHTML = [
    metric("Räume", data.room_count, `${data.open_valves} Ventile geöffnet`),
    metric("Ø Raumtemperatur", data.average_temperature == null ? "n/a" : `${data.average_temperature.toFixed(1)} °C`, "aktueller Bestand"),
    metric("Datenzugriff", "read-only", "keine Provider-Abfragen"),
    metric("Teststand", "0.10.0-dev", "Migration auf Port 8503")
  ].join("");
  document.querySelector("#content").innerHTML = `<section class="section"><h2>Raumstatus</h2><div class="rooms">${state.rooms.map(roomCard).join("")}</div></section>${heatPumpCard(data.heat_pump)}`;
}

function roomCard(room) {
  return `<button class="card room-card" data-room="${esc(room.room_name)}"><div class="room-name">${esc(room.room_name)}</div><div class="room-values"><span class="room-value">${room.current_temperature.toFixed(1)} °C</span><span class="room-value">Ziel ${room.target_temperature.toFixed(1)} °C</span><span class="room-value">${room.humidity.toFixed(0)} %</span></div><div class="room-detail">Ventil ${room.valve_position.toFixed(0)} % · ${esc(room.level)}</div></button>`;
}

function heatPumpCard(heatPump) {
  if (!heatPump) return '<section class="section"><h2>Wärmepumpe</h2><div class="card empty">Keine Wärmepumpendaten verfügbar.</div></section>';
  return `<section class="section"><h2>Wärmepumpe</h2><div class="card"><div class="room-name">${esc(heatPump.model)}</div><div class="room-values"><span class="room-value">Vorlauf ${heatPump.floor_supply_celsius ?? "n/a"} °C</span><span class="room-value">Puffer ${heatPump.buffer_celsius ?? "n/a"} °C</span><span class="room-value">Erzeugt heute ${heatPump.produced_energy_today_kwh.toFixed(1)} kWh</span></div><div class="room-detail">Modus ${esc(heatPump.operating_mode ?? "n/a")} · Verdichter ${heatPump.compressor_active ? "aktiv" : "bereit"}</div></div></section>`;
}

function chart(points) {
  if (!points.length) return '<p class="empty">Keine Historie für diesen Zeitraum verfügbar.</p>';
  const width = 760; const height = 250; const pad = 28;
  const values = points.flatMap((point) => [point.current_temperature, point.target_temperature]);
  const min = Math.floor(Math.min(...values) - 1); const max = Math.ceil(Math.max(...values) + 1);
  const x = (index) => pad + index * (width - pad * 2) / Math.max(1, points.length - 1);
  const y = (value) => height - pad - (value - min) * (height - pad * 2) / Math.max(1, max - min);
  const line = (key, color, dash = "") => `<polyline fill="none" stroke="${color}" stroke-width="3" ${dash ? `stroke-dasharray="${dash}"` : ""} points="${points.map((point, index) => `${x(index)},${y(point[key])}`).join(" ")}"/>`;
  return `<div class="chart-wrap"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Temperaturverlauf"><line x1="${pad}" y1="${height-pad}" x2="${width-pad}" y2="${height-pad}" stroke="#bcccdc"/><line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height-pad}" stroke="#bcccdc"/>${line("current_temperature", "#c2410c")}${line("target_temperature", "#64748b", "7 5")}<text x="${pad}" y="18" fill="#627d98" font-size="12">${max} °C</text><text x="${pad}" y="${height-4}" fill="#627d98" font-size="12">${min} °C</text></svg><div class="chart-legend"><span class="actual">Ist</span><span class="target">Ziel</span></div></div>`;
}

async function renderRoom(roomName) {
  const room = state.rooms.find((item) => item.room_name === roomName);
  const history = await getJson(`/api/v1/rooms/${encodeURIComponent(roomName)}/history?hours=24`);
  document.querySelector("#page-title").textContent = roomName;
  document.querySelector("#metrics").innerHTML = [
    metric("Ist", `${room.current_temperature.toFixed(1)} °C`, "aktueller Wert"),
    metric("Ziel", `${room.target_temperature.toFixed(1)} °C`, "Solltemperatur"),
    metric("Feuchte", `${room.humidity.toFixed(0)} %`, "aktuell"),
    metric("Ventil", `${room.valve_position.toFixed(0)} %`, room.level)
  ].join("");
  document.querySelector("#content").innerHTML = `<section class="section"><h2>Historie · letzte 24 Stunden</h2><div class="card">${chart(history)}</div></section><section class="section"><button class="back-button" data-view="home">← Zurück zur Übersicht</button></section>`;
}

function renderAllRooms() {
  document.querySelector("#page-title").textContent = "Alle Räume";
  document.querySelector("#metrics").innerHTML = "";
  document.querySelector("#content").innerHTML = `<section class="section"><h2>Raumvergleich</h2><div class="rooms">${state.rooms.map(roomCard).join("")}</div></section>`;
}

async function renderHeatPump() {
  const heatPump = await getJson("/api/v1/heat-pump");
  document.querySelector("#page-title").textContent = "Wärmepumpe";
  document.querySelector("#metrics").innerHTML = heatPump ? [metric("Vorlauf", `${heatPump.floor_supply_celsius ?? "n/a"} °C`, "Fußbodenheizung"), metric("Puffer", `${heatPump.buffer_celsius ?? "n/a"} °C`, "Sensorwert"), metric("Erzeugt heute", `${heatPump.produced_energy_today_kwh.toFixed(1)} kWh`, heatPump.model), metric("Modus", heatPump.operating_mode ?? "n/a", heatPump.compressor_active ? "Verdichter aktiv" : "Verdichter bereit")].join("") : "";
  document.querySelector("#content").innerHTML = `<section class="section"><h2>Wärmepumpenstatus</h2>${heatPump ? heatPumpCard(heatPump) : '<div class="card empty">Keine Wärmepumpendaten verfügbar.</div>'}</section>`;
}

async function render() {
  try {
    if (state.view === "room") await renderRoom(state.selectedRoom);
    else if (state.view === "rooms") renderAllRooms();
    else if (state.view === "heat-pump") await renderHeatPump();
    else renderHome();
    document.querySelectorAll("[data-room]").forEach((button) => button.addEventListener("click", () => { state.selectedRoom = button.dataset.room; state.view = "room"; render(); }));
    document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
  } catch (error) {
    document.querySelector("#content").innerHTML = `<div class="card error">Migration API nicht erreichbar: ${esc(error.message)}</div>`;
  }
}

Promise.all([getJson("/api/v1/home"), getJson("/api/v1/rooms")]).then(([home, rooms]) => { state.home = home; state.rooms = rooms; renderHeader(); render(); }).catch((error) => { document.querySelector("#freshness").textContent = `Migration API nicht erreichbar: ${error.message}`; });
