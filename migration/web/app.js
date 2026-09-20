const state = { home: null, rooms: [], view: "home", chartSeries: { current_temperature: true, target_temperature: true, humidity: true, valve_position: true } };
let chartsRenderGeneration = 0;
const isProduction = window.location.port === "8501";
const appLabel = isProduction ? "Produktiv" : "Migrationstest";
document.title = isProduction ? "HomeClimate Dashboard" : "HomeClimate Migration";

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
  document.querySelector("#app-version").textContent = `HomeClimate · ${appLabel}`;
  document.querySelector("#app-status").textContent = `${window.location.port || "80"} · API`;
  const formatFreshness = (timestamp) => {
    if (!timestamp) return "nicht verfügbar";
    const date = new Date(timestamp);
    const minutes = Math.max(0, Math.round((Date.now() - date.getTime()) / 60000));
    const formatted = date.toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" });
    return `${formatted} (vor ${minutes} Min.)`;
  };
  document.querySelector("#freshness").textContent = `Homematic: ${formatFreshness(state.home.latest_homematic)} · Viessmann: ${formatFreshness(state.home.latest_viessmann)}`;
}

function renderHome() {
  const data = state.home;
  document.querySelector("#page-title").textContent = "Dein Zuhause auf einen Blick";
  document.querySelector("#metrics").innerHTML = [
    metric("Räume", data.room_count, `${data.open_valves} Ventile geöffnet`),
    metric("Ø Raumtemperatur", data.average_temperature == null ? "n/a" : `${data.average_temperature.toFixed(1)} °C`, "aktueller Bestand"),
    metric("Datenzugriff", "read-only", "keine Provider-Abfragen"),
    metric(isProduction ? "Betriebsstand" : "Teststand", isProduction ? "Produktiv" : "Migration", `API auf Port ${window.location.port || "80"}`)
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

function chart(points, selectedSeries = state.chartSeries) {
  if (!points.length) return '<p class="empty">Keine Historie für diesen Zeitraum verfügbar.</p>';
  const width = 760; const height = 250; const pad = 28;
  const temperatureValues = points.flatMap((point) => [point.current_temperature, point.target_temperature].filter((_, index) => index === 0 ? selectedSeries.current_temperature : selectedSeries.target_temperature));
  const percentValues = points.flatMap((point) => [point.humidity, point.valve_position].filter((_, index) => index === 0 ? selectedSeries.humidity : selectedSeries.valve_position));
  const min = Math.floor(Math.min(...temperatureValues, 10) - 1); const max = Math.ceil(Math.max(...temperatureValues, 30) + 1);
  const x = (index) => pad + index * (width - pad * 2) / Math.max(1, points.length - 1);
  const y = (value) => height - pad - (value - min) * (height - pad * 2) / Math.max(1, max - min);
  const line = (key, color, dash = "", scale = y) => selectedSeries[key] ? `<polyline fill="none" stroke="${color}" stroke-width="3" ${dash ? `stroke-dasharray="${dash}"` : ""} points="${points.map((point, index) => `${x(index)},${scale(point[key])}`).join(" ")}"/>` : "";
  const percentScale = (value) => height - pad - value * (height - pad * 2) / 100;
  const tempTicks = [10, 15, 20, 25, 30].map((value) => `<line x1="${pad}" y1="${y(value)}" x2="${width-pad}" y2="${y(value)}" stroke="#e6edf3"/><text x="${pad-6}" y="${y(value)+4}" text-anchor="end" fill="#627d98" font-size="11">${value}</text>`).join("");
  const percentTicks = [0, 20, 40, 60, 80, 100].map((value) => `<text x="${width-pad+6}" y="${percentScale(value)+4}" fill="#627d98" font-size="11">${value}</text>`).join("");
  const timestamps = points.map((point) => new Date(point.recorded_at).getTime());
  const firstTimestamp = timestamps[0]; const lastTimestamp = timestamps[timestamps.length - 1];
  const firstFullHour = new Date(firstTimestamp); firstFullHour.setMinutes(0, 0, 0); if (firstFullHour.getTime() < firstTimestamp) firstFullHour.setHours(firstFullHour.getHours() + 1);
  const timeTicks = [];
  for (const tick = firstFullHour; tick.getTime() <= lastTimestamp; tick.setHours(tick.getHours() + 1)) {
    if (tick.getHours() % 4 !== 0) continue;
    const tickTime = tick.getTime();
    const ratio = (tickTime - firstTimestamp) / Math.max(1, lastTimestamp - firstTimestamp);
    timeTicks.push({ x: pad + ratio * (width - pad * 2), label: tick.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) });
  }
  const timeLabels = timeTicks.map((tick) => `<line x1="${tick.x}" y1="${pad}" x2="${tick.x}" y2="${height-pad}" stroke="#eef2f6"/><text x="${tick.x}" y="${height-5}" text-anchor="middle" fill="#627d98" font-size="10">${esc(tick.label)}</text>`).join("");
  const legend = [selectedSeries.current_temperature ? '<span style="color:#c2410c">Ist (°C)</span>' : "", selectedSeries.target_temperature ? '<span style="color:#64748b">Ziel (°C)</span>' : "", selectedSeries.humidity ? '<span style="color:#7c3aed">Feuchte (%)</span>' : "", selectedSeries.valve_position ? '<span style="color:#e03131">Ventil (%)</span>' : ""].join("");
  return `<div class="chart-wrap"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Raumverlauf mit Temperatur-, Feuchte- und Ventillinien">${tempTicks}<line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height-pad}" stroke="#9fb3c8"/><line x1="${width-pad}" y1="${pad}" x2="${width-pad}" y2="${height-pad}" stroke="#9fb3c8"/><line x1="${pad}" y1="${height-pad}" x2="${width-pad}" y2="${height-pad}" stroke="#9fb3c8"/>${percentTicks}${timeLabels}<text class="chart-axis-title" x="${pad}" y="12">Temperatur (°C)</text><text class="chart-axis-title" x="${width-pad}" y="12" text-anchor="end">Feuchte / Ventil (%)</text>${line("current_temperature", "#c2410c")}${line("target_temperature", "#64748b", "7 5")}${line("humidity", "#7c3aed", "", percentScale)}${line("valve_position", "#e03131", "2 2", percentScale)}</svg><div class="chart-legend">${legend}</div></div>`;
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
  const renderGeneration = ++chartsRenderGeneration;
  document.querySelector("#page-title").textContent = "Alle Diagramme";
  document.querySelector("#metrics").innerHTML = [metric("Diagramme", state.rooms.length, "alle Räume"), metric("Zeitraum", "24 h", "gemeinsame Auswahl"), metric("Messreihen", "Ist · Ziel", "Temperatur"), metric("Datenzugriff", "read-only", "keine Provider-Abfragen")].join("");
  const histories = await Promise.all(state.rooms.map(async (room) => ({ room, points: await getJson(`/api/v1/rooms/${encodeURIComponent(room.room_name)}/history?hours=24`) })));
  if (state.view !== "charts" || renderGeneration !== chartsRenderGeneration) return;
  const controls = Object.entries({ current_temperature: "Ist", target_temperature: "Ziel", humidity: "Feuchtigkeit", valve_position: "Ventil" }).map(([key, label]) => `<button class="${state.chartSeries[key] ? "active" : ""}" data-series="${key}">${label}</button>`).join("");
  document.querySelector("#content").innerHTML = `<section class="section"><h2>Raumverläufe · letzte 24 Stunden</h2><div class="series-controls" aria-label="Messreihen">${controls}</div><div class="chart-grid">${histories.map(({room, points}) => `<article class="card"><h2>${esc(room.room_name)}</h2>${chart(points)}</article>`).join("")}</div></section>`;
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
  const featureRows = report.features.map((feature) => `<tr><td>${esc(feature.feature)}</td><td>${esc(feature.property)}</td><td>${esc(feature.value)}</td><td>${esc(feature.unit)}</td></tr>`).join("");
  const curveOutdoor = Array.from({length: 10}, (_, index) => -20 + index * 5);
  const curveSlope = Number(metrics.curve_slope); const curveShift = Number(metrics.curve_shift);
  const curveSupply = (outdoor) => Math.max(10, Math.min(40, 20 + curveSlope * (20 - outdoor) + curveShift));
  const curvePoints = curveOutdoor.map((outdoor, index) => { const x = 80 + index * (620 / (curveOutdoor.length - 1)); const y = 225 - (curveSupply(outdoor) - 10) / 30 * 195; return `${x.toFixed(1)},${y.toFixed(1)}`; }).join(" ");
  const curve = `<svg viewBox="0 0 760 280" role="img" aria-label="Heizkurve mit Außentemperatur- und Vorlaufachsen"><g stroke="#e6edf3">${curveOutdoor.map((_, index) => `<line x1="${80 + index * (620 / (curveOutdoor.length - 1))}" y1="30" x2="${80 + index * (620 / (curveOutdoor.length - 1))}" y2="225"/>`).join("")}${[10,20,30,40].map((_, index) => `<line x1="80" y1="${225 - index * 65}" x2="700" y2="${225 - index * 65}"/>`).join("")}</g><line x1="80" y1="225" x2="700" y2="225" stroke="#7b8794"/><line x1="80" y1="30" x2="80" y2="225" stroke="#7b8794"/><polyline points="${curvePoints}" fill="none" stroke="#c2410c" stroke-width="4"/><g fill="#627d98" font-size="10" text-anchor="middle">${curveOutdoor.map((value, index) => `<text x="${80 + index * (620 / (curveOutdoor.length - 1))}" y="244">${value} °C</text>`).join("")}</g><g fill="#627d98" font-size="11" text-anchor="end">${[10,20,30,40].map((value, index) => `<text x="72" y="${229 - index * 65}">${value} °C</text>`).join("")}</g><text x="390" y="270" text-anchor="middle" fill="#52606d" font-size="12" font-weight="700">Außentemperatur (°C)</text><text x="15" y="130" text-anchor="middle" transform="rotate(-90 15 130)" fill="#52606d" font-size="12" font-weight="700">Vorlauf-Soll (°C)</text><text x="100" y="20" fill="#52606d" font-size="12" font-weight="700">Heizkurve · Steigung ${esc(metrics.curve_slope ?? "n/a")} · Shift ${esc(metrics.curve_shift ?? "n/a")}</text></svg>`;
  document.querySelector("#content").innerHTML = `<section class="section"><h2>Wärmepumpenstatus</h2><div class="card"><div class="room-name">${esc(report.model)} · ${report.online ? "Online" : "Offline"}</div><div class="room-detail">Betriebsmodus ${esc(metrics.operating_mode)} · Verdichter ${metrics.compressor_active ? "aktiv" : "bereit"}</div></div></section><section class="section"><h2>Anlagenbild</h2><div class="card schema-card">${heatPumpSchema(report, "anlage")}</div></section><section class="section"><h2>Viessmann-Komponentenbild</h2><div class="card schema-card">${heatPumpSchema(report, "komponenten")}</div></section><section class="section"><h2>Aktuelle Heizkurve</h2><div class="card schema-card">${curve}</div></section><section class="section"><details class="card"><summary>Technische Rohdaten · ${report.features.length} Werte</summary><div class="feature-table"><table><thead><tr><th>Feature</th><th>Property</th><th>Wert</th><th>Einheit</th></tr></thead><tbody>${featureRows}</tbody></table></div></details></section>`;
}

function heatPumpSchema(report, variant) {
  const map = Object.fromEntries(Object.values(report.system_map).flat().map((item) => [item.name, item]));
  const metrics = report.metrics;
  const value = (name) => { const raw = String(map[name]?.value || "nicht verfügbar").replace(" celsius", " °C").replace(" percent", " %"); return ({ heating: "Heizen", standby: "Bereitschaft", efficientwithmincomfort: "Komfortbetrieb", efficientWithMinComfort: "Komfortbetrieb", true: "Ja", false: "Nein" }[raw] || raw); };
  const state = (name) => String(map[name]?.state || "");
  const active = ["true", "on", "active", "heating"].includes(state("Verdichter").toLowerCase());
  const rod = ["true", "on", "active", "heating"].includes(state("Inneneinheit Heizstab").toLowerCase());
  const time = (feature) => { const raw = report.feature_timestamps?.[feature]; if (!raw) return "Zeitpunkt unbekannt"; const date = new Date(raw); return Number.isNaN(date.getTime()) ? raw : `${String(date.getUTCHours()).padStart(2, "0")}:${String(date.getUTCMinutes()).padStart(2, "0")} UTC`; };
  const featureValue = (feature, property = "value") => { const row = report.features.find((item) => item.feature === feature && item.property === property); return row ? `${row.value}${row.unit ? ` ${row.unit}` : ""}`.replace("celsius", "°C").replace("percent", "%").replace("revolutionsPerSecond", "1/s") : "nicht verfügbar"; };
  if (variant === "anlage") return `<svg viewBox="0 0 1280 640" role="img" aria-label="Produktionsnahes Heizungs- und Warmwasserschema"><defs><linearGradient id="buffer-${variant}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c51f1f"/><stop offset=".5" stop-color="#5b3d75"/><stop offset="1" stop-color="#1976d2"/></linearGradient></defs><g fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M245 260 H300 M490 300 H575 M735 330 H810 V330 H920" stroke="#a83b36" stroke-width="8"/><path d="M300 405 H245 M490 410 H575 M920 510 H810 V420 H735" stroke="#385b85" stroke-width="8"/><path d="M490 220 H535 V105 H575 M490 250 H550 V165 H575" stroke="#c98b4a" stroke-width="6"/><path d="M920 330 H1160 V365 H920 V400 H1160 V435 H920 V470 H1160 V505 H920" stroke="#a83b36" stroke-width="7"/><path d="M920 510 H1160" stroke="#385b85" stroke-width="7"/></g><g fill="#fff" stroke="#17202a" stroke-width="2"><rect x="35" y="170" width="210" height="245" rx="10"/><rect x="300" y="200" width="190" height="215" rx="10"/><rect x="575" y="255" width="160" height="190" rx="10" fill="url(#buffer-${variant})"/><rect x="575" y="35" width="160" height="190" rx="10" fill="url(#buffer-${variant})"/></g><g font-family="sans-serif" text-anchor="middle" fill="#17202a"><text x="140" y="205" font-weight="800">AUSSENEINHEIT</text><text x="140" y="230">${esc(report.model)}</text><text x="140" y="350">Verdichter ${active ? "aktiv" : "aus / bereit"}</text><text x="90" y="380">LÜFTER 1</text><text x="90" y="400" font-weight="700">${esc(value("Außenlüfter 1"))}</text><text x="190" y="380">LÜFTER 2</text><text x="190" y="400" font-weight="700">${esc(value("Außenlüfter 2"))}</text><text x="395" y="235" font-weight="800">INNENEINHEIT</text><text x="360" y="330">Pumpe ${esc(value("Inneneinheit Pumpe"))}</text><text x="430" y="335">HEIZSTAB</text><text x="430" y="355">${rod ? "bereit / heizt nicht" : "gesperrt"}</text><text x="655" y="292" font-weight="800">PUFFERSPEICHER</text><text x="655" y="420" font-weight="700">${esc(value("Pufferspeicher"))}</text><text x="655" y="438" font-size="11">Messwert ${esc(time("heating.bufferCylinder.sensors.temperature.main"))}</text><text x="655" y="72" font-weight="800">WARMWASSER</text><text x="655" y="94" font-weight="800">SPEICHER</text><text x="655" y="205" font-weight="700">${esc(value("Warmwasser"))}</text><circle cx="810" cy="135" r="18" fill="#fff7ed" stroke="#c98b4a"/><text x="810" y="182" font-size="11">ZIRKULATION</text><text x="810" y="198">${esc(value("Warmwasser-Zirkulation"))}</text><text x="820" y="305" font-weight="800">HEIZKREISPUMPE</text><text x="820" y="325">${esc(value("Heizkreis 1 Pumpe"))}</text><text x="1040" y="295" font-weight="800">FUSSBODENHEIZUNG</text><text x="1040" y="320" font-weight="700">Vorlauf ${esc(value("Heizkreis 1 Vorlauf"))}</text><text x="1040" y="338" font-size="11">Messwert ${esc(time("heating.circuits.0.sensors.temperature.supply"))}</text><text x="1040" y="550" font-weight="800">HEIZKREIS-RÜCKLAUF</text><text x="1040" y="570" font-size="11">kein separater Viessmann-Sensor</text></g></svg>`;
  return `<svg viewBox="0 0 1500 600" role="img" aria-label="Vollständiges Viessmann Komponentenbild"><defs><marker id="component-hot-final" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 z" fill="#a83b36"/></marker><marker id="component-cold-final" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 z" fill="#385b85"/></marker></defs><g fill="none" stroke-linecap="round" stroke-width="8"><path d="M245 95 H1120" stroke="#a83b36" marker-end="url(#component-hot-final)"/><path d="M1120 455 H245" stroke="#385b85" marker-end="url(#component-cold-final)"/><path d="M245 95 V175 H310 V350 H245 M245 350 V455 M540 95 V165 H700 V95 M700 95 V205 H540 V350 M700 95 H850 V180 H950 M950 350 H850 V455 H700 M1120 95 H1170 V180 H1250 M1250 440 H1170 V455 H1120" stroke="#a83b36"/></g><g fill="#fff" stroke="#17202a" stroke-width="2"><rect x="40" y="150" width="205" height="315" rx="10"/><rect x="170" y="175" width="60" height="180"/><rect x="400" y="210" width="150" height="130" rx="8"/><rect x="1200" y="180" width="230" height="260" rx="10"/><circle cx="90" cy="190" r="28"/><circle cx="90" cy="290" r="28"/><circle cx="90" cy="390" r="28"/></g><g font-family="sans-serif" text-anchor="middle" fill="#17202a"><text x="140" y="125" font-weight="800">AUSSENEINHEIT</text><text x="90" y="235">LÜFTER 1</text><text x="90" y="255" font-weight="700">${esc(value("Außenlüfter 1"))}</text><text x="90" y="335">LÜFTER 2</text><text x="90" y="355" font-weight="700">${esc(value("Außenlüfter 2"))}</text><text x="90" y="435">AUSSENLUFT</text><text x="90" y="455" font-weight="700">${esc(featureValue("heating.sensors.temperature.outside"))}</text><text x="200" y="390">Außen-</text><text x="200" y="410">temperatur</text><text x="475" y="355" font-weight="800">VERDICHTER</text><text x="475" y="378">${active ? "aktiv" : "bereit"} (${esc(value("Verdichter"))})</text><text x="475" y="400">Druck ${esc(featureValue("heating.compressors.0.sensors.pressure.inlet"))}</text><text x="700" y="55">Auslass ${esc(featureValue("heating.compressors.0.sensors.temperature.outlet"))}</text><text x="790" y="55">Drehzahl ${esc(featureValue("heating.compressors.0.speed.current"))}</text><text x="790" y="75">Motor ${esc(featureValue("heating.compressors.0.sensors.temperature.motorChamber"))}</text><text x="1000" y="175">Druck Eintritt</text><text x="1000" y="195">${esc(featureValue("heating.compressors.0.sensors.pressure.inlet"))}</text><text x="1000" y="315">Temperatur Eintritt</text><text x="1000" y="335">${esc(featureValue("heating.compressors.0.sensors.temperature.inlet"))}</text><text x="1315" y="220" font-weight="800">INNENEINHEIT</text><text x="1260" y="300">INTERNE PUMPE</text><text x="1260" y="322" font-weight="700">${esc(value("Inneneinheit Pumpe"))}</text><text x="1370" y="300">HEIZSTAB</text><text x="1370" y="322">${rod ? "bereit / aus" : "gesperrt"}</text><text x="1315" y="390" font-weight="700">Vorlauf ${esc(value("Heizkreis 1 Vorlauf"))}</text><text x="1315" y="410">Heizkreis 1</text></g></svg>`;
}

function legacyHeatPumpSchema(report, variant) {
  const map = Object.fromEntries(Object.values(report.system_map).flat().map((item) => [item.name, item]));
  const metrics = report.metrics;
  const value = (name) => { const raw = String(map[name]?.value || "nicht verfügbar").replace(" celsius", " °C").replace(" percent", " %"); return ({ heating: "Heizen", standby: "Bereitschaft", efficientwithmincomfort: "Komfortbetrieb", efficientWithMinComfort: "Komfortbetrieb", true: "Ja", false: "Nein" }[raw] || raw); };
  const state = (name) => String(map[name]?.state || "");
  const time = (feature) => { const raw = report.feature_timestamps?.[feature]; if (!raw) return "Zeitpunkt unbekannt"; const date = new Date(raw); return Number.isNaN(date.getTime()) ? raw : `${String(date.getUTCHours()).padStart(2, "0")}:${String(date.getUTCMinutes()).padStart(2, "0")} UTC`; };
  const active = ["true", "on", "active", "heating"].includes(state("Verdichter").toLowerCase());
  const rod = ["true", "on", "active", "heating"].includes(state("Inneneinheit Heizstab").toLowerCase());
  const clear = variant === "anlage";
  if (clear) return `<svg viewBox="0 0 1200 600" role="img" aria-label="Klar strukturiertes Viessmann Heizungs- und Warmwasserschema"><defs><linearGradient id="clear-buffer-gradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c51f1f"/><stop offset=".5" stop-color="#5b3d75"/><stop offset="1" stop-color="#1976d2"/></linearGradient><marker id="clear-arrow-hot" markerWidth="5" markerHeight="5" refX="4.5" refY="2.5" orient="auto"><path d="M0,0 L4.5,2.5 L0,5 z" fill="#a83b36"/></marker><marker id="clear-arrow-cold" markerWidth="5" markerHeight="5" refX="4.5" refY="2.5" orient="auto"><path d="M0,0 L4.5,2.5 L0,5 z" fill="#385b85"/></marker></defs><g fill="none" stroke-linecap="round" stroke-linejoin="round" stroke-width="7"><path d="M240 245 H290" stroke="#a83b36" marker-end="url(#clear-arrow-hot)"/><path d="M290 350 H240" stroke="#385b85" marker-end="url(#clear-arrow-cold)"/><path d="M490 300 H560" stroke="#a83b36" marker-end="url(#clear-arrow-hot)"/><path d="M490 380 H560" stroke="#385b85" marker-end="url(#clear-arrow-cold)"/><path d="M720 300 H780 V300 H900" stroke="#a83b36" marker-end="url(#clear-arrow-hot)"/><path d="M900 425 H760 V390 H720" stroke="#385b85" marker-end="url(#clear-arrow-cold)"/><path d="M490 220 H520 V100 H560 M490 250 H540 V160 H560" stroke="#c98b4a"/></g><g fill="#fff" stroke="#17202a" stroke-width="2"><rect x="40" y="170" width="200" height="240" rx="10"/><rect x="290" y="190" width="200" height="220" rx="10"/><rect x="560" y="250" width="160" height="180" rx="10" fill="url(#clear-buffer-gradient)"/><rect x="560" y="40" width="160" height="180" rx="10" fill="url(#clear-buffer-gradient)"/></g><g font-family="sans-serif" text-anchor="middle" fill="#17202a"><text x="140" y="205" font-weight="800">AUSSENEINHEIT</text><text x="140" y="228">${esc(report.model)}</text><text x="140" y="345">Verdichter ${active ? "aktiv" : "aus / bereit"}</text><text x="95" y="375">LÜFTER 1</text><text x="95" y="395" font-weight="700">${esc(value("Außenlüfter 1"))}</text><text x="185" y="375">LÜFTER 2</text><text x="185" y="395" font-weight="700">${esc(value("Außenlüfter 2"))}</text><text x="390" y="225" font-weight="800">INNENEINHEIT</text><text x="350" y="330">Pumpe ${esc(value("Inneneinheit Pumpe"))}</text><text x="430" y="335">HEIZSTAB</text><text x="430" y="353">${rod ? "bereit / heizt nicht" : "gesperrt"}</text><text x="640" y="285" font-weight="800">PUFFERSPEICHER</text><text x="640" y="410" font-weight="700">${esc(value("Pufferspeicher"))}</text><text x="640" y="427" font-size="11">Messwert ${esc(time("heating.bufferCylinder.sensors.temperature.main"))}</text><text x="640" y="75" font-weight="800">WARMWASSER</text><text x="640" y="94" font-weight="800">SPEICHER</text><text x="640" y="195" font-weight="700">${esc(value("Warmwasser"))}</text><text x="780" y="215" font-size="11">WARMWASSER-ZIRKULATION</text><text x="780" y="232">${esc(value("Warmwasser-Zirkulation"))}</text><text x="780" y="345">HEIZKREISPUMPE</text><text x="780" y="364" font-weight="700">${esc(value("Heizkreis 1 Pumpe"))}</text><text x="990" y="270" font-weight="800">FUSSBODENHEIZUNG</text><text x="990" y="288" font-weight="700">Vorlauf ${esc(value("Heizkreis 1 Vorlauf"))}</text><text x="990" y="305" font-size="11">Messwert ${esc(time("heating.circuits.0.sensors.temperature.supply"))}</text><text x="1100" y="450" font-size="11">HEIZKREIS-RÜCKLAUF</text><text x="1100" y="470" font-size="11">kein separater Viessmann-Sensor</text></g></svg>`;
  return `<svg viewBox="0 0 1400 520" role="img" aria-label="Vollständiges Viessmann Komponentenbild mit Außen- und Inneneinheit"><g fill="none" stroke-linecap="round" stroke-linejoin="round" stroke-width="7"><path d="M220 80 H1080" stroke="#a83b36"/><path d="M1080 360 H220" stroke="#385b85"/><path d="M220 80 V160 H300 V300 H220 M220 300 V360 M520 80 V150 H680 V80 M680 80 V180 H520 V300 M680 80 H820 V160 H900 M900 300 H820 V360 H680 M1080 80 H1120 V150 H1180 M1180 350 H1120 V360 H1080" stroke="#a83b36"/></g><g fill="#fff" stroke="#17202a" stroke-width="2" font-family="sans-serif" text-anchor="middle" fill="none"><rect x="390" y="165" width="130" height="110" rx="8"/><rect x="1180" y="150" width="180" height="200" rx="10"/><rect x="170" y="105" width="55" height="180"/><circle cx="75" cy="105" r="28"/><circle cx="75" cy="220" r="28"/></g><g font-family="sans-serif" text-anchor="middle" fill="#17202a"><text x="115" y="35" font-weight="800">AUSSENEINHEIT</text><text x="75" y="150">LÜFTER 1</text><text x="75" y="169" font-weight="700">${esc(value("Außenlüfter 1"))}</text><text x="75" y="265">LÜFTER 2</text><text x="75" y="284" font-weight="700">${esc(value("Außenlüfter 2"))}</text><text x="198" y="320">AUSSENLUFT</text><text x="198" y="339" font-weight="700">${esc(value("Außentemperatur"))}</text><text x="455" y="305" font-weight="800">VERDICHTER</text><text x="455" y="325">${active ? "aktiv" : "bereit"} (${esc(value("Verdichter"))})</text><text x="1270" y="180" font-weight="800">INNENEINHEIT</text><text x="1230" y="265">INTERNE PUMPE</text><text x="1230" y="284" font-weight="700">${esc(value("Inneneinheit Pumpe"))}</text><text x="1307" y="275">HEIZSTAB</text><text x="1307" y="294">${rod ? "bereit / aus" : "gesperrt"}</text><text x="1270" y="325">Vorlauf ${esc(value("Heizkreis 1 Vorlauf"))}</text></g></svg>`;
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
    document.querySelectorAll("[data-room]").forEach((button) => { button.onclick = () => { state.selectedRoom = button.dataset.room; state.view = "room"; render(); }; });
    document.querySelectorAll("[data-view]").forEach((button) => { button.onclick = () => setView(button.dataset.view); });
    document.querySelectorAll("[data-series]").forEach((button) => { button.onclick = () => { state.chartSeries[button.dataset.series] = !state.chartSeries[button.dataset.series]; button.classList.toggle("active", state.chartSeries[button.dataset.series]); render(); }; });
  } catch (error) {
    document.querySelector("#content").innerHTML = `<div class="card error">Migration API nicht erreichbar: ${esc(error.message)}</div>`;
  }
}

Promise.all([getJson("/api/v1/home"), getJson("/api/v1/rooms")]).then(([home, rooms]) => { state.home = home; state.rooms = rooms; renderHeader(); render(); }).catch((error) => { document.querySelector("#freshness").textContent = `Migration API nicht erreichbar: ${error.message}`; });
