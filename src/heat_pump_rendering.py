from __future__ import annotations

from datetime import datetime
from html import escape
from urllib.parse import quote

import pandas as pd
import streamlit as st

from src.viessmann_heatpump import feature_values, system_map


def render_embedded_html(markup: str, height: int) -> None:
    source = "data:text/html;charset=utf-8," + quote(markup)
    st.iframe(source, width="stretch", height=height)


def render_viessmann_heat_pumps(heat_pumps: list[object]) -> None:
    st.caption(f"{len(heat_pumps)} Viessmann heat pump(s), read-only")
    selected_index = st.selectbox(
        "Wärmepumpe auswählen",
        options=range(len(heat_pumps)),
        format_func=lambda index: (
            f"{heat_pumps[index].model} | {heat_pumps[index].device_id} | "
            f"{'online' if heat_pumps[index].online else 'offline'}"
        ),
        key="viessmann-heat-pump-report-selection",
    )
    snapshot = heat_pumps[selected_index]
    rows = feature_values(snapshot)
    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            width="stretch",
        )


def render_heat_pump_schema(snapshot: object) -> None:
    items = {item["name"]: item for group in system_map(snapshot).values() for item in group}

    def feature_time(feature_name: str) -> str:
        for feature in snapshot.features.get("data", []):
            if isinstance(feature, dict) and feature.get("feature") == feature_name:
                raw_timestamp = feature.get("timestamp")
                if raw_timestamp:
                    try:
                        timestamp = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
                        return timestamp.strftime("%H:%M")
                    except ValueError:
                        return str(raw_timestamp)
        return datetime.now().strftime("%H:%M")

    def value(name: str) -> str:
        raw_value = str(items.get(name, {}).get("value") or "nicht verfügbar")
        readable_value = raw_value.replace(" celsius", " °C").replace(" percent", " %")
        return {
            "heating": "Heizen",
            "standby": "Bereitschaft",
            "efficientwithmincomfort": "Komfortbetrieb",
            "true": "Ja",
            "false": "Nein",
        }.get(readable_value.lower(), readable_value)

    def state(name: str) -> str:
        return str(items.get(name, {}).get("state") or "")

    compressor_active = state("Verdichter").lower() in {"true", "on", "active", "heating"}
    heating_rod_ready = state("Inneneinheit Heizstab").lower() in {"true", "on", "active", "heating"}
    active_color = "#b43a32" if compressor_active else "#b9c2cc"
    dhw_color = "#c98b4a" if heating_rod_ready else "#b9c2cc"
    data_time = feature_time("heating.bufferCylinder.sensors.temperature.main")
    status_text = "aktiv" if compressor_active else "bereit"

    schema = f'''
        <style>
            html, body {{ margin: 0; background: #f7fafc; }}
            .schema-wrap {{ background: #f7fafc; overflow-x: auto; padding: 4px 0 0; }}
            .schema-header {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; margin: 0 4px 6px; padding: 0 0 7px; border-bottom: 1px solid #dfe7ef; }}
            .schema-header-title {{ font-family: sans-serif; color: #243b53; font-size: 0.72rem; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; }}
            .schema-header-meta {{ display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }}
            .schema-status-pill {{ display: inline-flex; align-items: center; gap: 6px; font-family: sans-serif; font-size: 11px; font-weight: 700; color: #52606d; }}
            .schema-status-dot {{ width: 7px; height: 7px; border-radius: 50%; background: {active_color}; }}
            .schema-legend {{ display: flex; align-items: center; gap: 9px; flex-wrap: wrap; font-family: sans-serif; font-size: 10px; color: #829ab1; }}
            .schema-legend-item {{ display: inline-flex; align-items: center; gap: 5px; }}
            .schema-swatch {{ width: 18px; height: 2px; display: inline-block; border: 0; }}
            .schema-swatch-hot {{ background: #a83b36; }}
            .schema-swatch-cold {{ background: #385b85; }}
            .schema-swatch-dhw {{ background: #c98b4a; }}
            .schema-svg {{ display: block; width: 100%; max-width: 100%; }}
            .schema-pipe {{ fill: none; stroke-linecap: round; stroke-linejoin: round; stroke-width: 5; }}
            .schema-pipe-hot {{ stroke: #a83b36; }}
            .schema-pipe-cold {{ stroke: #385b85; }}
            .schema-pipe-dhw {{ stroke: #c98b4a; }}
            .schema-box {{ fill: #fff; stroke: #cbd5e1; stroke-width: 1.5; }}
            .schema-buffer {{ fill: url(#schema-buffer-gradient); stroke: #cbd5e1; stroke-width: 1.5; }}
            .schema-dhw-box {{ fill: #fffaf3; stroke: #d9b37a; stroke-width: 1.5; }}
            .schema-title, .schema-label, .schema-value, .schema-state {{ font-family: sans-serif; paint-order: stroke fill; stroke: #f7fafc; stroke-width: 4px; stroke-linejoin: round; }}
            .schema-title {{ fill: #17202a; font-size: 14px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }}
            .schema-label {{ fill: #52606d; font-size: 10px; }}
            .schema-value {{ fill: #17202a; font-size: 14px; font-weight: 700; }}
            .schema-state {{ fill: #52606d; font-size: 11px; }}
            .schema-chip {{ fill: #fff; stroke: #dfe7ef; stroke-width: 1.4; }}
            .schema-chip-text {{ font-family: sans-serif; font-size: 9px; font-weight: 700; fill: #17202a; }}
        </style>
        <div class="schema-wrap">
          <div class="schema-header">
            <div class="schema-header-title">Viessmann Heizungslogik</div>
            <div class="schema-header-meta">
              <div class="schema-status-pill"><span class="schema-status-dot"></span>Betriebsstatus: {status_text}</div>
              <div class="schema-legend">
                <span class="schema-legend-item"><span class="schema-swatch schema-swatch-hot"></span>Vorlauf</span>
                <span class="schema-legend-item"><span class="schema-swatch schema-swatch-cold"></span>Rücklauf</span>
                <span class="schema-legend-item"><span class="schema-swatch schema-swatch-dhw"></span>Warmwasser</span>
                <span class="schema-legend-item">Datenstand {escape(data_time)}</span>
              </div>
            </div>
          </div>
          <svg class="schema-svg" viewBox="0 0 1200 520" role="img" aria-label="Klar strukturiertes Viessmann Heizungs- und Warmwasserschema">
            <defs>
              <linearGradient id="schema-buffer-gradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="#eaf1f8"/><stop offset="1" stop-color="#ddeaf5"/>
              </linearGradient>
              <marker id="schema-arrow-hot" markerWidth="5" markerHeight="5" refX="4.5" refY="2.5" orient="auto"><path d="M0,0 L4.5,2.5 L0,5 z" fill="#a83b36"/></marker>
              <marker id="schema-arrow-cold" markerWidth="5" markerHeight="5" refX="4.5" refY="2.5" orient="auto"><path d="M0,0 L4.5,2.5 L0,5 z" fill="#385b85"/></marker>
            </defs>
            <path d="M220 210 H300" class="schema-pipe schema-pipe-hot" marker-end="url(#schema-arrow-hot)"/>
            <path d="M300 290 H220" class="schema-pipe schema-pipe-cold" marker-end="url(#schema-arrow-cold)"/>
            <path d="M470 220 H550" class="schema-pipe schema-pipe-hot" marker-end="url(#schema-arrow-hot)"/>
            <path d="M550 300 H470" class="schema-pipe schema-pipe-cold" marker-end="url(#schema-arrow-cold)"/>
            <path d="M760 220 H830 V150 H900" class="schema-pipe schema-pipe-hot" marker-end="url(#schema-arrow-hot)"/>
            <path d="M900 350 H830 V280 H760" class="schema-pipe schema-pipe-cold" marker-end="url(#schema-arrow-cold)"/>
            <path d="M760 150 H900 V120 H1040" class="schema-pipe schema-pipe-dhw"/>

            <rect x="40" y="120" width="180" height="220" rx="12" class="schema-box"/>
            <text x="130" y="155" text-anchor="middle" class="schema-title">AUSSENEINHEIT</text>
            <text x="130" y="177" text-anchor="middle" class="schema-label">{escape(snapshot.model)}</text>
            <circle cx="130" cy="230" r="32" fill="none" stroke="{active_color}" stroke-width="8"/>
            <path d="M130 194 L143 230 L130 266 L117 230 Z" fill="{active_color}"/>
            <text x="130" y="290" text-anchor="middle" class="schema-state">Verdichter {status_text}</text>
            <rect x="76" y="306" width="52" height="18" rx="9" class="schema-chip"/>
            <text x="102" y="319" text-anchor="middle" class="schema-chip-text">L1 {escape(value("Außenlüfter 1"))}</text>
            <rect x="138" y="306" width="52" height="18" rx="9" class="schema-chip"/>
            <text x="164" y="319" text-anchor="middle" class="schema-chip-text">L2 {escape(value("Außenlüfter 2"))}</text>

            <rect x="300" y="150" width="170" height="180" rx="12" class="schema-box"/>
            <text x="385" y="185" text-anchor="middle" class="schema-title">INNENEINHEIT</text>
            <circle cx="330" cy="235" r="18" fill="#fff" stroke="#17202a" stroke-width="2"/>
            <path d="M321 235 Q330 220 339 235 Q330 250 321 235" fill="none" stroke="#17202a" stroke-width="3"/>
            <text x="360" y="232" text-anchor="start" class="schema-label">UMWÄLZPUMPE</text>
            <text x="360" y="250" text-anchor="start" class="schema-value">{escape(value("Inneneinheit Pumpe"))}</text>
            <path d="M330 265 L320 286 H329 L324 306 L342 278 H333 Z" fill="{dhw_color}"/>
            <text x="360" y="280" text-anchor="start" class="schema-label">ZUHEIZER</text>
            <text x="360" y="298" text-anchor="start" class="schema-state">{'bereit' if heating_rod_ready else 'gesperrt'}</text>

            <rect x="560" y="120" width="170" height="190" rx="12" class="schema-buffer"/>
            <text x="645" y="152" text-anchor="middle" class="schema-title">PUFFER</text>
            <path d="M585 200 H705 M585 240 H705 M585 280 H705" stroke="#f7fafc" stroke-width="5" fill="none" stroke-linecap="round"/>
            <text x="645" y="320" text-anchor="middle" class="schema-value">{escape(value("Pufferspeicher"))}</text>

            <rect x="900" y="35" width="170" height="120" rx="12" class="schema-dhw-box"/>
            <text x="985" y="68" text-anchor="middle" class="schema-title" style="font-size:11px;">WARMWASSER</text>
            <text x="985" y="92" text-anchor="middle" class="schema-value">{escape(value("Warmwasser"))}</text>
            <text x="985" y="108" text-anchor="middle" class="schema-label">Zirkulation {escape(value("Warmwasser-Zirkulation"))}</text>

            <rect x="900" y="300" width="230" height="120" rx="12" class="schema-box"/>
            <text x="1015" y="332" text-anchor="middle" class="schema-title" style="font-size:11px;">HEIZKREIS 1</text>
            <text x="1015" y="356" text-anchor="middle" class="schema-value">Vorlauf {escape(value("Heizkreis 1 Vorlauf"))}</text>
            <text x="1015" y="378" text-anchor="middle" class="schema-label">Anlagenrücklauf {escape(value("Heizungsrücklauf"))}</text>
          </svg>
        </div>
    '''
    render_embedded_html(schema, 620)


def render_clear_heat_pump_schema(snapshot: object) -> None:
    render_heat_pump_schema(snapshot)


def render_viessmann_component_schema(snapshot: object) -> None:
    rows = {(row["feature"], row["property"]): row for row in feature_values(snapshot)}

    def feature(feature_name: str, property_name: str) -> str:
        row = rows.get((feature_name, property_name))
        if not row or not row["value"]:
            return "nicht verfügbar"
        value_text = str(row["value"])
        return value_text.replace("celsius", "°C").replace("percent", "%")

    compressor_state = feature("heating.compressors.0", "phase")
    compressor_active = str(feature("heating.compressors.0", "active")).lower() == "true"
    compressor_display = f"aktiv ({compressor_state})" if compressor_active else f"bereit ({compressor_state})"
    schema = f'''
        <style>
            html, body {{ margin: 0; background: #f7fafc; }}
            .component-schema-wrap {{ background: #f7fafc; padding: 12px; overflow-x: auto; }}
            .component-schema {{ display: block; width: 100%; max-width: 100%; }}
            .component-pipe {{ fill: none; stroke-linecap: round; stroke-linejoin: round; stroke-width: 7; }}
            .component-hot {{ stroke: #a83b36; }}
            .component-cold {{ stroke: #385b85; }}
            .component-box {{ fill: #fff; stroke: #17202a; stroke-width: 2; }}
            .component-label, .component-value, .component-title {{ font-family: sans-serif; paint-order: stroke fill; stroke: #f7fafc; stroke-width: 5px; stroke-linejoin: round; }}
            .component-label {{ fill: #52606d; font-size: 12px; }}
            .component-value {{ fill: #17202a; font-size: 15px; font-weight: 700; }}
            .component-title {{ fill: #17202a; font-size: 14px; font-weight: 800; letter-spacing: .8px; }}
            .component-info {{ fill: #fff; stroke: #17202a; stroke-width: 3; }}
            .component-gauge {{ fill: #fff; stroke: #17202a; stroke-width: 2; }}
        </style>
        <div class="component-schema-wrap">
            <svg class="component-schema" viewBox="0 0 1400 520" role="img" aria-label="Vollständiges Viessmann Komponentenbild mit Außen- und Inneneinheit">
                <defs>
                    <marker id="component-arrow-hot" markerWidth="5" markerHeight="5" refX="4.5" refY="2.5" orient="auto"><path d="M0,0 L4.5,2.5 L0,5 z" fill="#a83b36"/></marker>
                    <marker id="component-arrow-cold" markerWidth="5" markerHeight="5" refX="4.5" refY="2.5" orient="auto"><path d="M0,0 L4.5,2.5 L0,5 z" fill="#385b85"/></marker>
                </defs>
                <path d="M220 80 H1080" class="component-pipe component-hot" marker-end="url(#component-arrow-hot)"/>
                <path d="M1080 360 H220" class="component-pipe component-cold" marker-end="url(#component-arrow-cold)"/>
                <path d="M220 80 V160 H300 V300 H220" class="component-pipe component-hot"/>
                <path d="M220 300 V360" class="component-pipe component-cold"/>
                <path d="M520 80 V150 H680 V80" class="component-pipe component-hot"/>
                <path d="M680 80 V180 H520 V300" class="component-pipe component-cold"/>
                <path d="M680 80 H820 V160 H900" class="component-pipe component-hot"/>
                <path d="M900 300 H820 V360 H680" class="component-pipe component-cold"/>
                <path d="M1080 80 H1120 V150 H1180" class="component-pipe component-hot"/>
                <path d="M1180 350 H1120 V360 H1080" class="component-pipe component-cold"/>

                <text x="115" y="35" text-anchor="middle" class="component-title">AUSSENEINHEIT</text>
                <circle cx="75" cy="105" r="28" class="component-info"/>
                <path d="M61 105 Q75 82 89 105 Q75 128 61 105" fill="none" stroke="#17202a" stroke-width="4"/>
                <text x="75" y="150" text-anchor="middle" class="component-label">LÜFTER 1</text>
                <text x="75" y="169" text-anchor="middle" class="component-value">{escape(feature("heating.primaryCircuit.fans.0.current", "value"))}</text>
                <circle cx="75" cy="220" r="28" class="component-info"/>
                <path d="M61 220 Q75 197 89 220 Q75 243 61 220" fill="none" stroke="#17202a" stroke-width="4"/>
                <text x="75" y="265" text-anchor="middle" class="component-label">LÜFTER 2</text>
                <text x="75" y="284" text-anchor="middle" class="component-value">{escape(feature("heating.primaryCircuit.fans.1.current", "value"))}</text>
                <rect x="170" y="105" width="55" height="180" class="component-box"/>
                <path d="M178 125 H217 M178 145 H217 M178 165 H217 M178 185 H217 M178 205 H217 M178 225 H217 M178 245 H217" stroke="#a4adb8" stroke-width="3"/>
                <text x="198" y="320" text-anchor="middle" class="component-label">AUSSENLUFT</text>
                <text x="198" y="339" text-anchor="middle" class="component-value">{escape(feature("heating.sensors.temperature.outside", "value"))}</text>

                <rect x="390" y="165" width="130" height="110" rx="8" class="component-box"/>
                <circle cx="455" cy="220" r="30" class="component-info"/>
                <path d="M438 220 L455 195 L472 220 L455 245 Z" fill="{'#a83b36' if compressor_active else '#b9c2cc'}"/>
                <text x="455" y="305" text-anchor="middle" class="component-title">VERDICHTER</text>
                <text x="455" y="325" text-anchor="middle" class="component-label">{escape(compressor_display)}</text>
                <text x="455" y="345" text-anchor="middle" class="component-value">{escape(feature("heating.compressors.0.sensors.pressure.inlet", "value"))}</text>

                <circle cx="610" cy="80" r="18" class="component-info"/><text x="610" y="87" text-anchor="middle" class="component-title" style="font-size:16px">i</text>
                <text x="610" y="45" text-anchor="middle" class="component-value">{escape(feature("heating.compressors.0.sensors.temperature.outlet", "value"))}</text>
                <rect x="640" y="48" width="80" height="40" class="component-box"/><text x="680" y="74" text-anchor="middle" class="component-value">{escape(feature("heating.compressors.0.speed.current", "value"))}</text>
                <circle cx="760" cy="80" r="18" class="component-info"/><text x="760" y="87" text-anchor="middle" class="component-title" style="font-size:16px">i</text>
                <text x="760" y="45" text-anchor="middle" class="component-value">{escape(feature("heating.compressors.0.sensors.temperature.motorChamber", "value"))}</text>

                <circle cx="1000" cy="360" r="24" class="component-gauge"/><path d="M987 360 Q1000 342 1013 360 Q1000 378 987 360" fill="none" stroke="#17202a" stroke-width="3"/>
                <text x="1000" y="405" text-anchor="middle" class="component-label">PRIMÄRPUMPE</text>
                <text x="1000" y="425" text-anchor="middle" class="component-value">{escape(feature("heating.boiler.pumps.internal.current", "value"))}</text>
                <circle cx="920" cy="170" r="24" class="component-gauge"/><text x="920" y="178" text-anchor="middle" class="component-title" style="font-size:16px">≈</text>
                <text x="920" y="215" text-anchor="middle" class="component-value">{escape(feature("heating.compressors.0.sensors.pressure.inlet", "value"))}</text>
                <text x="920" y="235" text-anchor="middle" class="component-label">DRUCK EINTRITT</text>
                <circle cx="920" cy="280" r="24" class="component-gauge"/><text x="920" y="288" text-anchor="middle" class="component-title" style="font-size:16px">≈</text>
                <text x="920" y="325" text-anchor="middle" class="component-value">{escape(feature("heating.compressors.0.sensors.temperature.inlet", "value"))}</text>
                <text x="920" y="345" text-anchor="middle" class="component-label">TEMPERATUR EINTRITT</text>

                <rect x="1180" y="150" width="180" height="200" rx="10" class="component-box"/>
                <text x="1270" y="180" text-anchor="middle" class="component-title">INNENEINHEIT</text>
                <circle cx="1230" cy="225" r="22" class="component-info"/>
                <path d="M1218 225 Q1230 208 1242 225 Q1230 242 1218 225" fill="none" stroke="#17202a" stroke-width="3"/>
                <text x="1230" y="265" text-anchor="middle" class="component-label">INTERNE PUMPE</text>
                <text x="1230" y="284" text-anchor="middle" class="component-value">{escape(feature("heating.boiler.pumps.internal.current", "value"))}</text>
                <path d="M1305 205 L1294 230 H1304 L1298 254 L1320 222 H1310 Z" fill="#c98b4a"/>
                <text x="1307" y="275" text-anchor="middle" class="component-label">HEIZSTAB</text>
                <text x="1307" y="294" text-anchor="middle" class="component-label">bereit / aus</text>
                <text x="1270" y="325" text-anchor="middle" class="component-label">Vorlauf {escape(feature("heating.circuits.0.sensors.temperature.supply", "value"))}</text>
            </svg>
        </div>
    '''
    render_embedded_html(schema, 500)


def render_heating_curve(snapshot: object) -> None:
    values = {(row["feature"], row["property"]): row["value"] for row in feature_values(snapshot)}
    slope = values.get(("heating.circuits.0.heating.curve", "slope"))
    shift = values.get(("heating.circuits.0.heating.curve", "shift"))
    try:
        slope = float(slope) if slope is not None else None
        shift = float(shift) if shift is not None else None
    except (TypeError, ValueError):
        slope = None
        shift = None
    st.markdown("### Aktuelle Heizkurve")
    st.caption("Heizkreis 1, direkt aus dem aktuellen Viessmann-Snapshot.")
    columns = st.columns(2)
    with columns[0]:
        st.metric("Steigung", f"{slope} " if slope is not None else "nicht verfügbar")
    with columns[1]:
        st.metric("Niveau / Shift", f"{shift} °C" if shift is not None else "nicht verfügbar")
    if isinstance(slope, (int, float)) and isinstance(shift, (int, float)):
        outdoor_temperatures = list(range(-20, 26, 5))
        supply_targets = [
            max(10.0, min(40.0, 20.0 + float(slope) * (20.0 - outdoor_temperature) + float(shift)))
            for outdoor_temperature in outdoor_temperatures
        ]
        chart_points = []
        x_step = 416 / max(1, len(supply_targets) - 1)
        for index, supply_target in enumerate(supply_targets):
            x_position = 58 + index * x_step
            y_position = 205 - (supply_target - 10.0) / 30.0 * 165
            chart_points.append((x_position, y_position, outdoor_temperatures[index], supply_target))
        curve_path = " ".join(
            f"{'M' if index == 0 else 'L'} {x_position:.1f} {y_position:.1f}"
            for index, (x_position, y_position, _, _) in enumerate(chart_points)
        )
        curve_markers = "".join(
            f'<circle cx="{x_position:.1f}" cy="{y_position:.1f}" r="4" fill="#a83b36"/>'
            for x_position, y_position, _, _ in chart_points
        )
        curve_labels = "".join(
            f'<text x="{x_position:.1f}" y="235" text-anchor="middle">{outdoor_temperature}°</text>'
            for x_position, _, outdoor_temperature, _ in chart_points
        )
        curve_markup = f'''
            <style>
              body {{ margin: 0; background: #f3f7fb; font-family: sans-serif; }}
              svg {{ display: block; width: 100%; height: 260px; }}
              .axis {{ stroke: #829ab1; stroke-width: 1.5; }}
              .grid {{ stroke: #d9e2ec; stroke-width: 1; }}
              text {{ fill: #486581; font-size: 12px; }}
              .axis-title {{ fill: #243b53; font-size: 13px; font-weight: 700; }}
              .curve {{ fill: none; stroke: #a83b36; stroke-width: 3; stroke-linejoin: round; stroke-linecap: round; }}
            </style>
            <svg viewBox="0 0 520 260" role="img" aria-label="Heizkurve: Vorlauf-Solltemperatur in Abhängigkeit von der Außentemperatur">
              <line x1="58" y1="40" x2="58" y2="205" class="axis"/>
              <line x1="58" y1="205" x2="474" y2="205" class="axis"/>
              <line x1="58" y1="40" x2="474" y2="40" class="grid"/>
              <line x1="58" y1="122" x2="474" y2="122" class="grid"/>
              <line x1="58" y1="205" x2="474" y2="205" class="grid"/>
              <text x="48" y="45" text-anchor="end">40°C</text>
              <text x="48" y="127" text-anchor="end">25°C</text>
              <text x="48" y="210" text-anchor="end">10°C</text>
              <path d="{curve_path}" class="curve"/>
              {curve_markers}
              {curve_labels}
              <text x="265" y="258" text-anchor="middle" class="axis-title">Außentemperatur</text>
              <text x="14" y="125" text-anchor="middle" transform="rotate(-90 14 125)" class="axis-title">Vorlauf-Soll</text>
            </svg>
        '''
        render_embedded_html(curve_markup, 275)
