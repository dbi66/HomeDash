const SVG_NS = "http://www.w3.org/2000/svg";
const canvas = document.querySelector("#schema-canvas");
const nodesLayer = document.querySelector("#nodes-layer");
const edgesLayer = document.querySelector("#edges-layer");
const gridPattern = document.querySelector("#grid-pattern");
function loadSavedSchemas() {
  try {
    const saved = JSON.parse(localStorage.getItem("homedash-schema-editor") || "null");
    return Array.isArray(saved) && saved.length ? saved : [starterSchema()];
  } catch (error) {
    return [starterSchema()];
  }
}
const state = {
  schemas: loadSavedSchemas(), activeSchemaIndex: 0, selectedId: null, tool: "select", dragging: null,
  connectingId: null, grid: true, gridSnap: true, objectSnap: true, gridSize: 20,
};
Object.defineProperty(state, "schema", { get: () => state.schemas[state.activeSchemaIndex], set: (value) => { state.schemas[state.activeSchemaIndex] = value; } });

function starterSchema() {
  return { schema_version: 1, name: "Wärmepumpenanlage", viewport: { width: 1200, height: 700 }, nodes: [
    node("outdoor", "outdoor", "Außeneinheit", 70, 265, 190, 120, "heating.compressors.0", "active"),
    node("unit", "unit", "Inneneinheit", 330, 250, 210, 150, "heating.boiler.pumps.internal", "current"),
    node("buffer", "tank", "Pufferspeicher", 650, 175, 190, 230, "heating.bufferCylinder.sensors.temperature.main", "value"),
    node("dhw", "dhw", "Warmwasserspeicher", 920, 160, 190, 180, "heating.dhw.sensors.temperature.dhwCylinder", "value"),
    node("circuit", "circuit", "Heizkreis", 650, 475, 250, 115, "heating.circuits.0.sensors.temperature.supply", "value"),
  ], edges: [edge("outdoor-unit", "outdoor", "unit"), edge("unit-buffer", "unit", "buffer"), edge("buffer-circuit", "buffer", "circuit"), edge("unit-dhw", "unit", "dhw")] };
}

function hydraulicSchema() {
  return { schema_version: 1, name: "Hydraulikbild · Sensorlayout", viewport: { width: 1200, height: 700 }, nodes: [
    node("outside-temperature", "sensor", "Außenluft", 35, 265, 150, 72, "heating.sensors.temperature.outside", "value"),
    node("fan-1", "sensor", "Lüfter 1", 80, 85, 150, 72, "heating.primaryCircuit.fans.0.current", "value"),
    node("fan-2", "sensor", "Lüfter 2", 80, 505, 150, 72, "heating.primaryCircuit.fans.1.current", "value"),
    node("evaporator", "unit", "Wärmetauscher", 285, 245, 175, 145, "heating.sensors.temperature.outside", "value"),
    node("compressor", "outdoor", "Verdichter", 505, 265, 175, 125, "heating.compressors.0", "phase"),
    node("compressor-status", "sensor", "Verdichterstatus", 490, 85, 180, 72, "heating.compressors.0", "active"),
    node("pressure-inlet", "sensor", "Druck Eintritt", 730, 85, 180, 72, "heating.compressors.0.sensors.pressure.inlet", "value"),
    node("temperature-outlet", "sensor", "Temperatur Auslass", 730, 185, 180, 72, "heating.compressors.0.sensors.temperature.outlet", "value"),
    node("temperature-motor", "sensor", "Motortemperatur", 730, 285, 180, 72, "heating.compressors.0.sensors.temperature.motorChamber", "value"),
    node("temperature-inlet", "sensor", "Temperatur Eintritt", 730, 385, 180, 72, "heating.compressors.0.sensors.temperature.inlet", "value"),
    node("supply", "circuit", "Vorlauf", 965, 135, 175, 90, "heating.boiler.sensors.temperature.commonSupply", "value"),
    node("return", "circuit", "Rücklauf", 965, 475, 175, 90, "heating.sensors.temperature.return", "value"),
    node("buffer", "tank", "Pufferspeicher", 965, 280, 175, 120, "heating.bufferCylinder.sensors.temperature.main", "value"),
  ], edges: [
    edge("air-evaporator", "outside-temperature", "evaporator"), edge("evaporator-compressor", "evaporator", "compressor"), edge("compressor-supply", "compressor", "supply"), edge("supply-buffer", "supply", "buffer"), edge("buffer-return", "buffer", "return"), edge("compressor-inlet", "compressor", "temperature-inlet"), edge("outlet-pressure", "temperature-outlet", "pressure-inlet")
  ] };
}

function node(id, type, label, x, y, width, height, binding, property) { return { id, type, label, x, y, width, height, binding: { feature: binding, property, unit: "" } }; }
function edge(id, source, target) { return { id, source, target, kind: "hydraulic" }; }
function setStatus(message) { document.querySelector("#status-message").textContent = message; }
function selectedNode() { return state.schema.nodes.find((item) => item.id === state.selectedId); }
function snap(value) { return state.gridSnap ? Math.round(value / state.gridSize) * state.gridSize : value; }
function center(item) { return { x: item.x + item.width / 2, y: item.y + item.height / 2 }; }
function pointerPosition(event) { const point = canvas.createSVGPoint(); point.x = event.clientX; point.y = event.clientY; return point.matrixTransform(canvas.getScreenCTM().inverse()); }

function render() {
  localStorage.setItem("homedash-schema-editor", JSON.stringify(state.schemas));
  refreshSchemaSelect();
  canvas.setAttribute("viewBox", `0 0 ${state.schema.viewport.width} ${state.schema.viewport.height}`);
  gridPattern.setAttribute("width", state.gridSize); gridPattern.setAttribute("height", state.gridSize);
  document.querySelector("#canvas-background").setAttribute("fill", state.grid ? "url(#grid-pattern)" : "#f7fbfc");
  edgesLayer.replaceChildren(); nodesLayer.replaceChildren();
  state.schema.edges.forEach((item) => renderEdge(item));
  state.schema.nodes.forEach((item) => renderNode(item));
  updateInspector();
}

function renderEdge(item) {
  const source = state.schema.nodes.find((nodeItem) => nodeItem.id === item.source); const target = state.schema.nodes.find((nodeItem) => nodeItem.id === item.target); if (!source || !target) return;
  const start = center(source); const end = center(target); const line = document.createElementNS(SVG_NS, "path");
  line.setAttribute("d", `M ${start.x} ${start.y} C ${(start.x + end.x) / 2} ${start.y}, ${(start.x + end.x) / 2} ${end.y}, ${end.x} ${end.y}`); line.setAttribute("class", `edge${state.selectedId === item.id ? " selected" : ""}`); line.dataset.edgeId = item.id; line.addEventListener("click", (event) => { event.stopPropagation(); state.selectedId = item.id; render(); }); edgesLayer.append(line);
}

function renderNode(item) {
  const group = document.createElementNS(SVG_NS, "g"); group.dataset.nodeId = item.id; group.setAttribute("class", `node${state.selectedId === item.id || state.connectingId === item.id ? " selected" : ""}`); group.setAttribute("transform", `translate(${item.x} ${item.y})`); group.addEventListener("pointerdown", (event) => beginDrag(event, item)); group.addEventListener("click", (event) => { event.stopPropagation(); if (state.tool === "connect") connectNode(item.id); else selectNode(item.id); });
  const body = document.createElementNS(SVG_NS, "rect"); body.setAttribute("class", "node-body"); body.setAttribute("filter", "url(#shadow)"); body.setAttribute("width", item.width); body.setAttribute("height", item.height); body.setAttribute("rx", 10); group.append(body);
  const shape = document.createElementNS(SVG_NS, "rect"); shape.setAttribute("class", "node-shape"); shape.setAttribute("x", 16); shape.setAttribute("y", 17); shape.setAttribute("width", Math.min(52, item.width - 32)); shape.setAttribute("height", Math.min(52, item.height - 34)); shape.setAttribute("rx", item.type === "tank" || item.type === "dhw" ? 24 : 5); group.append(shape);
  const title = text(item.label, 80, 35, "node-title"); group.append(title); group.append(text(typeLabel(item.type), 80, 55, "node-type"));
  const binding = item.binding?.feature || "placeholder.feature"; group.append(text(`${binding}.${item.binding?.property || "value"}`, 16, item.height - 18, "node-binding"));
  [[0, item.height / 2], [item.width, item.height / 2]].forEach(([x, y]) => { const anchor = document.createElementNS(SVG_NS, "circle"); anchor.setAttribute("class", "node-anchor"); anchor.setAttribute("cx", x); anchor.setAttribute("cy", y); group.append(anchor); }); nodesLayer.append(group);
}
function text(value, x, y, className) { const element = document.createElementNS(SVG_NS, "text"); element.textContent = value; element.setAttribute("x", x); element.setAttribute("y", y); element.setAttribute("class", className); return element; }
function typeLabel(type) { return ({ tank: "Speicher", unit: "Inneneinheit", outdoor: "Außeneinheit", circuit: "Heizkreis", dhw: "Warmwasser", sensor: "Messpunkt" })[type] || "Komponente"; }
function selectNode(id) { state.selectedId = id; state.tool = "select"; document.querySelector("#select-tool").classList.add("active"); document.querySelector("#connect-tool").classList.remove("active"); render(); }
function connectNode(id) { if (!state.connectingId) { state.connectingId = id; setStatus("Zielkomponente auswählen"); render(); return; } if (state.connectingId !== id) { const exists = state.schema.edges.some((item) => item.source === state.connectingId && item.target === id); if (!exists) state.schema.edges.push(edge(`edge-${Date.now()}`, state.connectingId, id)); setStatus(exists ? "Verbindung existiert bereits" : "Verbindung angelegt"); } state.connectingId = null; state.selectedId = id; render(); }

function beginDrag(event, item) {
  if (state.tool !== "select") return;
  event.preventDefault(); selectNode(item.id); const pointer = pointerPosition(event); state.dragging = { item, offsetX: pointer.x - item.x, offsetY: pointer.y - item.y }; canvas.setPointerCapture(event.pointerId);
  canvas.addEventListener("pointermove", dragNode); canvas.addEventListener("pointerup", endDrag, { once: true });
}
function dragNode(event) { if (!state.dragging) return; const pointer = pointerPosition(event); let x = snap(pointer.x - state.dragging.offsetX); let y = snap(pointer.y - state.dragging.offsetY); if (state.objectSnap) ({ x, y } = objectSnap(state.dragging.item, x, y)); state.dragging.item.x = Math.max(0, Math.min(state.schema.viewport.width - state.dragging.item.width, x)); state.dragging.item.y = Math.max(0, Math.min(state.schema.viewport.height - state.dragging.item.height, y)); render(); }
function endDrag(event) { state.dragging = null; canvas.releasePointerCapture(event.pointerId); canvas.removeEventListener("pointermove", dragNode); setStatus("Position übernommen"); }
function objectSnap(item, x, y) {
  const threshold = 12; const others = state.schema.nodes.filter((candidate) => candidate.id !== item.id); const candidatesX = [x, x + item.width / 2, x + item.width].flatMap((value) => others.flatMap((other) => [other.x, other.x + other.width / 2, other.x + other.width].map((target) => ({ delta: target - value, value })))); const candidatesY = [y, y + item.height / 2, y + item.height].flatMap((value) => others.flatMap((other) => [other.y, other.y + other.height / 2, other.y + other.height].map((target) => ({ delta: target - value, value })))); const best = (list) => list.filter((candidate) => Math.abs(candidate.delta) <= threshold).sort((a, b) => Math.abs(a.delta) - Math.abs(b.delta))[0]; const xMatch = best(candidatesX); const yMatch = best(candidatesY); return { x: xMatch ? x + xMatch.delta : x, y: yMatch ? y + yMatch.delta : y };
}

function updateInspector() { const item = selectedNode(); const form = document.querySelector("#inspector-form"); document.querySelector("#inspector").classList.toggle("hidden", Boolean(item)); form.classList.toggle("hidden", !item); document.querySelector("#inspector-title").textContent = item ? item.label : "Nichts ausgewählt"; if (!item) return; ["label", "key", "x", "y", "width", "height"].forEach((field) => { const input = document.querySelector(`#node-${field}`); input.value = field === "key" ? item.id : item[field]; }); document.querySelector("#node-binding").value = item.binding?.feature || ""; document.querySelector("#node-property").value = item.binding?.property || "value"; }
function refreshSchemaSelect() { const select = document.querySelector("#schema-select"); select.replaceChildren(); state.schemas.forEach((schema, index) => { const option = document.createElement("option"); option.value = index; option.textContent = `${index + 1}: ${schema.name || "Unbenanntes Schema"}`; select.append(option); }); select.value = state.activeSchemaIndex; }
function switchSchema(index) { state.activeSchemaIndex = Number(index); state.selectedId = null; state.connectingId = null; document.querySelector("#schema-name").value = state.schema.name || "Wärmepumpenanlage"; render(); setStatus(`Schema ${state.activeSchemaIndex + 1} aktiviert`); }
function addTemplate() { const template = document.querySelector("#template-select").value === "hydraulikbild" ? hydraulicSchema() : starterSchema(); state.schemas.push(template); state.activeSchemaIndex = state.schemas.length - 1; state.selectedId = null; document.querySelector("#schema-name").value = template.name; render(); setStatus(`Vorlage als Schema ${state.activeSchemaIndex + 1} geladen`); }
function applyInspector() { const item = selectedNode(); if (!item) return; const oldId = item.id; item.label = document.querySelector("#node-label").value.trim() || "Unbenannte Komponente"; item.id = document.querySelector("#node-key").value.trim().replace(/[^a-zA-Z0-9_-]/g, "-") || item.id; if (item.id !== oldId) state.schema.edges.forEach((connection) => { if (connection.source === oldId) connection.source = item.id; if (connection.target === oldId) connection.target = item.id; }); item.x = Number(document.querySelector("#node-x").value) || 0; item.y = Number(document.querySelector("#node-y").value) || 0; item.width = Math.max(80, Number(document.querySelector("#node-width").value) || 160); item.height = Math.max(50, Number(document.querySelector("#node-height").value) || 100); item.binding = { feature: document.querySelector("#node-binding").value.trim() || "placeholder.feature", property: document.querySelector("#node-property").value.trim() || "value", unit: "" }; state.selectedId = item.id; render(); setStatus("Komponente aktualisiert"); }
function addNode(type, x = 400, y = 200) { const id = `${type}-${Date.now()}`; const item = node(id, type, typeLabel(type), snap(x), snap(y), type === "circuit" ? 240 : 180, type === "circuit" ? 110 : 130, `placeholder.${type}`, "value"); state.schema.nodes.push(item); selectNode(id); setStatus("Platzhalter hinzugefügt"); }
function removeSelected() { if (!state.selectedId) return; state.schema.nodes = state.schema.nodes.filter((item) => item.id !== state.selectedId); state.schema.edges = state.schema.edges.filter((item) => item.source !== state.selectedId && item.target !== state.selectedId); state.selectedId = null; render(); setStatus("Auswahl gelöscht"); }
function exportSchema() { const blob = new Blob([JSON.stringify(state.schema, null, 2)], { type: "application/json" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `${state.schema.name.toLowerCase().replace(/[^a-z0-9]+/g, "-") || "homedash-schema"}.json`; link.click(); URL.revokeObjectURL(link.href); setStatus("JSON exportiert"); }
async function publishSchema() { const button = document.querySelector("#production-button"); button.disabled = true; setStatus("Produktionsschema wird gespeichert ..."); try { const target = document.querySelector("#publish-target").value; const response = await fetch("/api/save-schema", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ target, schema: state.schema }) }); if (!response.ok) throw new Error(await response.text() || `HTTP ${response.status}`); setStatus(`${target === "functional" ? "Funktionssicht" : "Hydrauliksicht"} bereitgestellt`); } catch (error) { setStatus(`Bereitstellung fehlgeschlagen: ${error.message}`); } finally { button.disabled = false; } }
function importSchema(file) { const reader = new FileReader(); reader.onload = () => { try { const value = JSON.parse(reader.result); if (!value || !Array.isArray(value.nodes) || !Array.isArray(value.edges)) throw new Error("nodes oder edges fehlen"); state.schemas.push(value); state.activeSchemaIndex = state.schemas.length - 1; state.selectedId = null; document.querySelector("#schema-name").value = value.name || "Wärmepumpenanlage"; render(); setStatus(`Schema ${state.activeSchemaIndex + 1} geladen`); } catch (error) { setStatus(`Import fehlgeschlagen: ${error.message}`); } }; reader.readAsText(file); }
async function loadProductionSchemas() { try { const response = await fetch("/api/schemas"); if (!response.ok) throw new Error(`HTTP ${response.status}`); const payload = await response.json(); if (!Array.isArray(payload.schemas) || payload.schemas.length === 0) throw new Error("Keine Produktionsschemata"); state.schemas = payload.schemas.map((item) => item.schema); state.activeSchemaIndex = 0; state.selectedId = null; render(); setStatus("Produktionsschemata geladen"); } catch (error) { setStatus(`Produktionsschemata nicht geladen: ${error.message}`); } }

document.querySelector("#schema-canvas").addEventListener("click", () => { state.selectedId = null; render(); });
document.querySelector("#apply-node").addEventListener("click", applyInspector); document.querySelector("#delete-button").addEventListener("click", removeSelected); document.querySelector("#production-button").addEventListener("click", publishSchema); document.querySelector("#export-button").addEventListener("click", exportSchema); document.querySelector("#template-button").addEventListener("click", addTemplate); document.querySelector("#reset-button").addEventListener("click", () => { state.schema = starterSchema(); state.selectedId = null; document.querySelector("#schema-name").value = state.schema.name; render(); setStatus("Beispiel wiederhergestellt"); });
document.querySelector("#schema-name").addEventListener("input", (event) => { state.schema.name = event.target.value || "Wärmepumpenanlage"; refreshSchemaSelect(); }); document.querySelector("#schema-select").addEventListener("change", (event) => switchSchema(event.target.value)); document.querySelector("#import-file").addEventListener("change", (event) => { if (event.target.files[0]) { importSchema(event.target.files[0]); event.target.value = ""; } });
document.querySelector("#grid-toggle").addEventListener("change", (event) => { state.grid = event.target.checked; render(); }); document.querySelector("#grid-snap-toggle").addEventListener("change", (event) => { state.gridSnap = event.target.checked; }); document.querySelector("#object-snap-toggle").addEventListener("change", (event) => { state.objectSnap = event.target.checked; }); document.querySelector("#grid-size").addEventListener("change", (event) => { state.gridSize = Math.max(4, Math.min(80, Number(event.target.value) || 20)); event.target.value = state.gridSize; render(); });
document.querySelector("#select-tool").addEventListener("click", () => { state.tool = "select"; state.connectingId = null; document.querySelector("#select-tool").classList.add("active"); document.querySelector("#connect-tool").classList.remove("active"); render(); }); document.querySelector("#connect-tool").addEventListener("click", () => { state.tool = "connect"; state.connectingId = null; setStatus("Startkomponente auswählen"); document.querySelector("#connect-tool").classList.add("active"); document.querySelector("#select-tool").classList.remove("active"); render(); });
document.querySelectorAll(".palette-item").forEach((button) => { button.addEventListener("dragstart", (event) => event.dataTransfer.setData("text/plain", button.dataset.type)); button.addEventListener("click", () => addNode(button.dataset.type)); });
canvas.addEventListener("dragover", (event) => event.preventDefault()); canvas.addEventListener("drop", (event) => { event.preventDefault(); const type = event.dataTransfer.getData("text/plain"); if (!type) return; const point = pointerPosition(event); addNode(type, point.x - 80, point.y - 55); });
render();
loadProductionSchemas();