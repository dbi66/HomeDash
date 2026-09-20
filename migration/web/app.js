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
  if (state.view !== "room" || state.selectedRoom !== roomName) return;
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

function renderRoomReport() {
  document.querySelector("#page-title").textContent = "Raumbericht";
  document.querySelector("#metrics").innerHTML = [
    metric("Räume", state.rooms.length, "aktueller Bestand"),
    metric("Ø Temperatur", `${state.home.average_temperature.toFixed(1)} °C`, "alle Räume"),
    metric("Offene Ventile", state.home.open_valves, "aktueller Status"),
    metric("Datenzugriff", "read-only", "produktiver Datenbestand")
  ].join("");
  const rows = state.rooms.map((room) => `<tr><td>${esc(room.room_name)}</td><td>${room.current_temperature.toFixed(1)} °C</td><td>${room.target_temperature.toFixed(1)} °C</td><td>${room.humidity.toFixed(0)} %</td><td>${room.valve_position.toFixed(0)} %</td><td>${esc(room.level)}</td></tr>`).join("");
  document.querySelector("#content").innerHTML = `<section class="section"><h2>Aktuelle Raumwerte</h2><div class="card"><table class="report-table"><thead><tr><th>Raum</th><th>Ist</th><th>Ziel</th><th>Feuchte</th><th>Ventil</th><th>Etage</th></tr></thead><tbody>${rows}</tbody></table></div></section><section class="section"><h2>Raumprofile</h2><div class="chart-grid"><article class="card"><h2>IST-Temperatur</h2>${spiderChart(state.rooms, "current_temperature", 10, 30, "#c2410c")}</article><article class="card"><h2>Feuchtigkeit</h2>${spiderChart(state.rooms, "humidity", 0, 100, "#7c3aed")}</article></div></section>`;
}

function spiderChart(readings, key, minimum, maximum, color) {
  const width = 520; const height = 360; const centerX = 260; const centerY = 170; const radius = 120;
  const point = (value, index, scale) => { const angle = index * Math.PI * 2 / readings.length - Math.PI / 2; const distance = radius * scale; return `${centerX + Math.cos(angle) * distance},${centerY + Math.sin(angle) * distance}`; };
  const rings = [0.25, 0.5, 0.75, 1].map((scale) => `<circle cx="${centerX}" cy="${centerY}" r="${radius * scale}" fill="none" stroke="#d9e2ec"/>`).join("");
  const axes = readings.map((reading, index) => { const angle = index * Math.PI * 2 / readings.length - Math.PI / 2; return `<line x1="${centerX}" y1="${centerY}" x2="${centerX + Math.cos(angle) * radius}" y2="${centerY + Math.sin(angle) * radius}" stroke="#d9e2ec"/><text x="${centerX + Math.cos(angle) * (radius + 25)}" y="${centerY + Math.sin(angle) * (radius + 25)}" text-anchor="middle" fill="#627d98" font-size="10">${esc(reading.room_name)}</text>`; }).join("");
  const values = readings.map((reading, index) => point(reading[key], index, Math.max(0, Math.min(1, (reading[key] - minimum) / (maximum - minimum))))).join(" ");
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Spiderchart">${rings}${axes}<polygon points="${values}" fill="${color}" fill-opacity=".18" stroke="${color}" stroke-width="3"/></svg>`;
}

async function renderCharts() {
  document.querySelector("#page-title").textContent = "Alle Diagramme";
  document.querySelector("#metrics").innerHTML = [metric("Diagramme", state.rooms.length, "alle Räume"), metric("Zeitraum", "24 h", "gemeinsame Auswahl"), metric("Messreihen", "Ist · Ziel", "Temperatur"), metric("Datenzugriff", "read-only", "keine Provider-Abfragen")].join("");
  const histories = await Promise.all(state.rooms.map(async (room) => ({ room, points: await getJson(`/api/v1/rooms/${encodeURIComponent(room.room_name)}/history?hours=24`) })));
  if (state.view !== "charts") return;
  document.querySelector("#content").innerHTML = `<section class="section"><h2>Raumverläufe · letzte 24 Stunden</h2><div class="chart-grid">${histories.map(({room, points}) => `<article class="card"><h2>${esc(room.room_name)}</h2>${chart(points)}</article>`).join("")}</div></section>`;
}

async function renderWeather() {
  const weather = await getJson("/api/v1/weather");
  if (state.view !== "weather") return;
  const daily = weather.daily;
  document.querySelector("#page-title").textContent = "Wetterbericht";
  document.querySelector("#metrics").innerHTML = [metric("Ort", weather.location, "Open-Meteo"), metric("Tage", daily.time.length, "Vorhersage"), metric("Heute", `${daily.temperature_2m_max[0]} / ${daily.temperature_2m_min[0]} °C`, "Maximum / Minimum"), metric("Regen", `${daily.precipitation_sum[0]} mm`, "heute")].join("");
  const days = daily.time.map((date, index) => `<article class="card forecast-day"><div class="room-name">${esc(index === 0 ? "Heute" : date)}</div><div class="metric-value">${esc(daily.temperature_2m_max[index])} / ${esc(daily.temperature_2m_min[index])} °C</div><div class="metric-detail">Regen ${esc(daily.precipitation_sum[index])} mm · Wind ${esc(daily.wind_speed_10m_max[index])} km/h</div></article>`).join("");
  document.querySelector("#content").innerHTML = `<section class="section"><h2>7-Tage-Wetterbericht · ${esc(weather.location)}</h2><div class="forecast-grid">${days}</div></section>`;
}

async function renderHeatPump() {
  const report = await getJson("/api/v1/heat-pump/report");
  if (state.view !== "heat-pump") return;
  document.querySelector("#page-title").textContent = "Wärmepumpe";
  if (!report) { document.querySelector("#metrics").innerHTML = ""; document.querySelector("#content").innerHTML = '<div class="card empty">Keine Wärmepumpendaten verfügbar.</div>'; return; }
  const metrics = report.metrics;
  document.querySelector("#metrics").innerHTML = [metric("Vorlauf", `${metrics.floor_supply_celsius ?? "n/a"} °C`, "Fußbodenheizung"), metric("Puffer", `${metrics.buffer_celsius ?? "n/a"} °C`, "Sensorwert"), metric("Erzeugt heute", `${metrics.produced_energy_today_kwh.toFixed(1)} kWh`, report.model), metric("SPF gesamt", metrics.spf_total ?? "n/a", "aktuell"), metric("Verdichterstarts", metrics.starts_24h ?? "n/a", "letzte 24 Stunden"), metric("Ø Zyklus", metrics.average_cycle_minutes == null ? "n/a" : `${metrics.average_cycle_minutes.toFixed(1)} min`, "je Start"), metric("Energie zugeführt", `${metrics.supplied_energy_today_kwh.toFixed(1)} kWh`, "heute"), metric("Wärmeleistung", `${metrics.current_heat_kw ?? "n/a"} kW`, "aktuell")].join("");
  document.querySelector("#content").innerHTML = `<section class="section"><h2>Wärmepumpenstatus</h2><div class="card"><div class="room-name">${esc(report.model)} · ${report.online ? "Online" : "Offline"}</div><div class="room-detail">Betriebsmodus ${esc(metrics.operating_mode)} · Verdichter ${metrics.compressor_active ? "aktiv" : "bereit"}</div></div></section><section class="section"><h2>Anlagenbild</h2><div class="card schema-card">${heatPumpSchema(report, "anlage")}</div></section><section class="section"><h2>Viessmann-Komponentenbild</h2><div class="card schema-card">${heatPumpSchema(report, "komponenten")}</div></section>`;
}

function heatPumpSchema(report, variant) {
  const metrics = report.metrics;
  const accent = variant === "anlage" ? "#a83b36" : "#385b85";
  return `<svg viewBox="0 0 900 300" role="img" aria-label="Wärmepumpenschema"><defs><marker id="arrow-${variant}" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 z" fill="${accent}"/></marker></defs><path d="M120 150 H270 V80 H610 V150 H780" fill="none" stroke="${accent}" stroke-width="8" marker-end="url(#arrow-${variant})"/><path d="M780 190 H610 V250 H270 V190 H120" fill="none" stroke="#385b85" stroke-width="8" marker-end="url(#arrow-${variant})"/><rect x="35" y="105" width="170" height="90" rx="8" fill="#fff" stroke="#17202a" stroke-width="2"/><text x="120" y="132" text-anchor="middle" font-weight="800">AUSSENEINHEIT</text><text x="120" y="158" text-anchor="middle">${esc(report.model)}</text><text x="120" y="180" text-anchor="middle">${metrics.compressor_active ? "Verdichter aktiv" : "Verdichter bereit"}</text><rect x="315" y="55" width="180" height="200" rx="8" fill="#fff" stroke="#17202a" stroke-width="2"/><text x="405" y="88" text-anchor="middle" font-weight="800">${variant === "anlage" ? "PUFFER" : "INNENEINHEIT"}</text><text x="405" y="145" text-anchor="middle" font-size="28">${variant === "anlage" ? `${metrics.buffer_celsius ?? "n/a"} °C` : `${metrics.floor_supply_celsius ?? "n/a"} °C`}</text><text x="405" y="175" text-anchor="middle">${variant === "anlage" ? "Pufferspeicher" : "Heizkreis-Vorlauf"}</text><rect x="610" y="105" width="170" height="90" rx="8" fill="#fff" stroke="#17202a" stroke-width="2"/><text x="695" y="138" text-anchor="middle" font-weight="800">${variant === "anlage" ? "HEIZKREIS" : "WÄRMEPUMPE"}</text><text x="695" y="165" text-anchor="middle">${metrics.operating_mode}</text></svg>`;
}

async function render() {
  try {
    if (state.view === "room") await renderRoom(state.selectedRoom);
    else if (state.view === "rooms") renderAllRooms();
    else if (state.view === "room-report") renderRoomReport();
    else if (state.view === "charts") await renderCharts();
    else if (state.view === "heat-pump") await renderHeatPump();
    else if (state.view === "weather") await renderWeather();
    else renderHome();
    document.querySelectorAll("[data-room]").forEach((button) => button.addEventListener("click", () => { state.selectedRoom = button.dataset.room; state.view = "room"; render(); }));
    document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
  } catch (error) {
    document.querySelector("#content").innerHTML = `<div class="card error">Migration API nicht erreichbar: ${esc(error.message)}</div>`;
  }
}

Promise.all([getJson("/api/v1/home"), getJson("/api/v1/rooms")]).then(([home, rooms]) => { state.home = home; state.rooms = rooms; renderHeader(); render(); }).catch((error) => { document.querySelector("#freshness").textContent = `Migration API nicht erreichbar: ${error.message}`; });
