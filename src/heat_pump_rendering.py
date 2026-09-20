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
            column_config={
                "feature": "Feature",
                "property": "Property",
                "value": "Value",
                "unit": "Unit",
            },
        )
    else:
        st.info("No flattened feature values were returned for this heat pump.")
    with st.expander("Complete raw Viessmann data"):
        st.json(snapshot.features)


def render_heat_pump_schema(snapshot: object) -> None:
    items = {item["name"]: item for group in system_map(snapshot).values() for item in group}

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

    def sensor(x: int, y: int, label: str, reading: str, color: str = "#17202a") -> str:
        return (
            f'<circle cx="{x}" cy="{y}" r="16" fill="#fff" stroke="{color}" stroke-width="3"/>'
            f'<text x="{x}" y="{y + 6}" text-anchor="middle" class="schema-sensor">i</text>'
            f'<text x="{x}" y="{y + 38}" text-anchor="middle" class="schema-label">{escape(label)}</text>'
            f'<text x="{x}" y="{y + 57}" text-anchor="middle" class="schema-reading">{escape(reading)}</text>'
        )

    active_color = "#b43a32" if state("Verdichter").lower() in {"true", "on", "active", "heating"} else "#b9c2cc"
    compressor_state = "aktiv" if active_color == "#b43a32" else "aus / bereit"
    heating_rod_ready = state("Inneneinheit Heizstab").lower() in {"true", "on", "active", "heating"}
    heating_rod_color = "#c98b4a" if heating_rod_ready else "#b9c2cc"
    heating_rod_state = "bereit / heizt nicht" if heating_rod_ready else "gesperrt"
    schema = f'''
        <style>
            html, body {{ margin: 0; background: #f7fafc; }}
            .heat-pump-schema-wrap {{ background: #f7fafc; padding: 8px; overflow-x: auto; }}
            .heat-pump-schema {{ display: block; min-width: 0; max-width: 100%; width: 100%; }}
            .schema-pipe {{ fill: none; stroke-linecap: round; stroke-linejoin: round; stroke-width: 8; }}
            .schema-hot {{ stroke: #a83b36; }} .schema-cold {{ stroke: #385b85; }}
            .schema-dhw-pipe {{ fill: none; stroke: #c98b4a; stroke-linecap: round; stroke-linejoin: round; stroke-width: 5; }}
            .schema-device, .schema-tank, .schema-dhw {{ fill: #fff; stroke: #17202a; stroke-width: 2; }}
            .schema-buffer {{ fill: url(#schema-buffer-gradient); stroke: #17202a; stroke-width: 2; }}
            .schema-dhw {{ fill: #fff7ed; stroke: #17202a; stroke-width: 2; }}
            .schema-tank-line {{ stroke: #9aa5b1; stroke-width: 2; }}
            .schema-buffer-coil {{ fill: none; stroke: #f7fafc; stroke-width: 5; stroke-linecap: round; }}
            .schema-pump {{ fill: #fff; stroke: #17202a; stroke-width: 3; }}
            .schema-title, .schema-subtitle, .schema-label, .schema-reading, .schema-state, .schema-sensor {{ font-family: sans-serif; }}
            .schema-title, .schema-subtitle, .schema-label, .schema-reading, .schema-state {{ paint-order: stroke fill; stroke: #f7fafc; stroke-width: 5px; stroke-linejoin: round; }}
            .schema-title {{ fill: #17202a; font-size: 14px; font-weight: 800; letter-spacing: 1px; }}
            .schema-subtitle, .schema-label {{ fill: #52606d; font-size: 12px; }}
            .schema-reading {{ fill: #17202a; font-size: 15px; font-weight: 700; }}
            .schema-state {{ fill: #7b8794; font-size: 12px; }} .schema-sensor {{ fill: #17202a; font-size: 17px; font-weight: 800; }}
        </style>
        <div class="heat-pump-schema-wrap">
    <svg class="heat-pump-schema" viewBox="0 0 1200 500" role="img" aria-label="Hydraulisches Schema der Wärmepumpe">
        <defs>
          <marker id="schema-arrow-red" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#a83b36"/></marker>
          <marker id="schema-arrow-blue" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#385b85"/></marker>
                    <linearGradient id="schema-buffer-gradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stop-color="#c51f1f"/>
                        <stop offset="0.48" stop-color="#5b3d75"/>
                        <stop offset="1" stop-color="#1976d2"/>
                    </linearGradient>
        </defs>
        <path d="M420 180 V125 H400 V170 H920" class="schema-pipe schema-hot" marker-end="url(#schema-arrow-red)"/>
        <path d="M920 80 V385 H720 V430 H420 V300" class="schema-pipe schema-cold" marker-end="url(#schema-arrow-blue)"/>
        <path d="M400 80 V230 H510 V385" class="schema-pipe schema-hot"/>
        <path d="M510 385 V230 H400" class="schema-pipe schema-cold"/>
        <path d="M720 430 V310 H610 V230" class="schema-pipe schema-cold"/>
        <path d="M610 230 H720 V125" class="schema-pipe schema-hot"/>
        <path d="M720 170 V125" class="schema-pipe schema-hot"/>
        <path d="M720 125 V260 H820" class="schema-pipe schema-hot"/>
        <path d="M820 380 H720 V430" class="schema-pipe schema-cold"/>

        <rect x="72" y="145" width="190" height="225" rx="8" class="schema-device"/>
        <text x="167" y="182" text-anchor="middle" class="schema-title">AUSSENEINHEIT</text>
        <text x="167" y="207" text-anchor="middle" class="schema-subtitle">{escape(snapshot.model)}</text>
        <circle cx="167" cy="256" r="31" fill="none" stroke="{active_color}" stroke-width="8"/>
        <path d="M167 225 L177 256 L167 287 L157 256 Z" fill="{active_color}"/>
        <text x="167" y="312" text-anchor="middle" class="schema-state">Verdichter {compressor_state}</text>
        <text x="112" y="340" text-anchor="middle" class="schema-label" style="font-size:10px">LÜFTER 1</text>
        <text x="112" y="356" text-anchor="middle" class="schema-reading" style="font-size:13px">{escape(value("Außenlüfter 1"))}</text>
        <text x="185" y="340" text-anchor="middle" class="schema-label" style="font-size:10px">LÜFTER 2</text>
        <text x="185" y="356" text-anchor="middle" class="schema-reading" style="font-size:13px">{escape(value("Außenlüfter 2"))}</text>

        <path d="M262 225 H280" class="schema-pipe schema-hot"/>
        <path d="M262 300 H280" class="schema-pipe schema-cold"/>
        <rect x="280" y="210" width="140" height="120" rx="8" class="schema-device"/>
        <text x="350" y="238" text-anchor="middle" class="schema-title" style="font-size:11px">INNENEINHEIT</text>
        <circle cx="320" cy="270" r="20" class="schema-pump"/>
        <path d="M309 270 Q320 254 331 270 Q320 286 309 270" fill="none" stroke="#17202a" stroke-width="2"/>
        <text x="320" y="306" text-anchor="middle" class="schema-state">Pumpe {escape(value("Inneneinheit Pumpe"))}</text>
        <path d="M390 250 L380 270 H389 L384 290 L402 265 H393 Z" fill="{heating_rod_color}"/>
        <text x="390" y="306" text-anchor="middle" class="schema-label" style="font-size:9px">HEIZSTAB</text>
        <text x="390" y="320" text-anchor="middle" class="schema-state" style="font-size:9px">{heating_rod_state}</text>

        <rect x="440" y="155" width="140" height="230" rx="8" class="schema-buffer"/>
        <text x="510" y="185" text-anchor="middle" class="schema-title">PUFFER</text>
        <path d="M460 220 H560 M460 270 H560 M460 320 H560" class="schema-tank-line"/>
        <path d="M468 250 C550 225 550 285 468 270 C550 250 550 310 468 295" class="schema-buffer-coil"/>
        <text x="510" y="365" text-anchor="middle" class="schema-reading">{escape(value("Pufferspeicher"))}</text>

        <circle cx="720" cy="125" r="28" class="schema-pump"/>
        <path d="M705 125 Q720 104 735 125 Q720 146 705 125" fill="none" stroke="#17202a" stroke-width="3"/>
        <text x="720" y="170" text-anchor="middle" class="schema-label">Heizkreispumpe</text>
        <text x="720" y="190" text-anchor="middle" class="schema-reading">{escape(value("Heizkreis 1 Pumpe"))}</text>

        <circle cx="610" cy="230" r="28" class="schema-pump"/>
        <path d="M595 230 Q610 209 625 230 Q610 251 595 230" fill="none" stroke="#17202a" stroke-width="3"/>
        <text x="610" y="263" text-anchor="middle" class="schema-label">Interne Pumpe</text>
        <text x="610" y="283" text-anchor="middle" class="schema-reading">{escape(value("Interne Pumpe"))}</text>

        <path d="M820 260 H980 V280 H820 V300 H980 V320 H820" class="schema-pipe schema-hot"/>
        <path d="M820 320 H980 V340 H820 V360 H980 V380 H820" class="schema-pipe schema-cold"/>
        <text x="900" y="410" text-anchor="middle" class="schema-title" style="font-size:11px">FUSSBODENHEIZUNG</text>
        <text x="900" y="430" text-anchor="middle" class="schema-reading">Vorlauf {escape(value("Heizkreis 1 Vorlauf"))}</text>

        <path d="M580 58 Q640 35 700 58 V130 Q640 153 580 130 Z" class="schema-dhw"/>
        <ellipse cx="640" cy="58" rx="60" ry="23" class="schema-dhw"/>
        <path d="M580 130 Q640 107 700 130" fill="none" stroke="#c98b4a" stroke-width="2"/>
        <text x="640" y="78" text-anchor="middle" class="schema-title" style="font-size:11px">WARMWASSER</text>
        <text x="640" y="94" text-anchor="middle" class="schema-title" style="font-size:11px">SPEICHER</text>
        <text x="640" y="119" text-anchor="middle" class="schema-reading">{escape(value("Warmwasser"))}</text>
        <path d="M640 153 V190 H820 V215 H640 V153" class="schema-dhw-pipe"/>
        <circle cx="820" cy="202" r="16" fill="#fff7ed" stroke="#c98b4a" stroke-width="3"/>
        <path d="M812 202 Q820 192 828 202 Q820 212 812 202" fill="none" stroke="#c98b4a" stroke-width="2"/>
        <text x="980" y="215" text-anchor="middle" class="schema-label" style="font-size:10px">HAUSINTERNE ZIRKULATION</text>
        <text x="980" y="230" text-anchor="middle" class="schema-state">{escape(value("Warmwasser-Zirkulation"))}</text>

        {sensor(320, 125, "Gemeinsamer Vorlauf", value("Gemeinsamer Vorlauf"), "#a83b36")}
        {sensor(400, 80, "Außentemperatur", value("Außentemperatur"), "#385b85")}
        {sensor(510, 430, "Pufferspeicher", value("Pufferspeicher"), "#385b85")}
        {sensor(1010, 260, "Heizkreis Vorlauf", value("Heizkreis 1 Vorlauf"), "#a83b36")}
        {sensor(1040, 385, "Anlagenrücklauf", value("Gemeinsamer Vorlauf"), "#385b85")}
      </svg>
    </div>
    '''
    render_embedded_html(schema, 520)


def render_clear_heat_pump_schema(snapshot: object) -> None:
    items = {item["name"]: item for group in system_map(snapshot).values() for item in group}

    def feature_time(feature_name: str) -> str:
        for feature in snapshot.features.get("data", []):
            if isinstance(feature, dict) and feature.get("feature") == feature_name:
                raw_timestamp = feature.get("timestamp")
                if raw_timestamp:
                    try:
                        timestamp = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
                        return timestamp.strftime("%H:%M UTC")
                    except ValueError:
                        return str(raw_timestamp)
        return "Zeitpunkt unbekannt"

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
    rod_ready = state("Inneneinheit Heizstab").lower() in {"true", "on", "active", "heating"}
    schema = f'''
        <style>
            html, body {{ margin: 0; background: #f7fafc; }}
            .clear-schema-wrap {{ background: #f7fafc; padding: 12px; overflow-x: auto; }}
            .clear-schema {{ display: block; width: 100%; max-width: 100%; }}
            .clear-pipe {{ fill: none; stroke-linecap: round; stroke-linejoin: round; stroke-width: 7; }}
            .clear-hot {{ stroke: #a83b36; }} .clear-cold {{ stroke: #385b85; }} .clear-dhw {{ stroke: #c98b4a; }}
            .clear-box {{ fill: #fff; stroke: #17202a; stroke-width: 2; }}
            .clear-buffer {{ fill: url(#clear-buffer-gradient); stroke: #17202a; stroke-width: 2; }}
            .clear-floor {{ fill: none; stroke-linecap: round; stroke-width: 6; }}
            .clear-floor-hot {{ stroke: #a83b36; }} .clear-floor-cold {{ stroke: #385b85; }}
            .clear-title, .clear-label, .clear-value, .clear-state {{ font-family: sans-serif; paint-order: stroke fill; stroke: #f7fafc; stroke-width: 5px; stroke-linejoin: round; }}
            .clear-title {{ fill: #17202a; font-size: 15px; font-weight: 800; letter-spacing: .8px; }}
            .clear-label {{ fill: #52606d; font-size: 12px; }}
            .clear-value {{ fill: #17202a; font-size: 15px; font-weight: 700; }}
            .clear-state {{ fill: #52606d; font-size: 11px; }}
            .clear-sensor {{ fill: #fff; stroke: #17202a; stroke-width: 2; }}
        </style>
        <div class="clear-schema-wrap">
            <svg class="clear-schema" viewBox="0 0 1200 600" role="img" aria-label="Klar strukturiertes Viessmann Heizungs- und Warmwasserschema">
                <defs>
                    <linearGradient id="clear-buffer-gradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stop-color="#c51f1f"/><stop offset="0.5" stop-color="#5b3d75"/><stop offset="1" stop-color="#1976d2"/>
                    </linearGradient>
                      <marker id="clear-arrow-hot" markerWidth="5" markerHeight="5" refX="4.5" refY="2.5" orient="auto"><path d="M0,0 L4.5,2.5 L0,5 z" fill="#a83b36"/></marker>
                      <marker id="clear-arrow-cold" markerWidth="5" markerHeight="5" refX="4.5" refY="2.5" orient="auto"><path d="M0,0 L4.5,2.5 L0,5 z" fill="#385b85"/></marker>
                </defs>

                <path d="M240 245 H290" class="clear-pipe clear-hot" marker-end="url(#clear-arrow-hot)"/>
                <path d="M290 350 H240" class="clear-pipe clear-cold" marker-end="url(#clear-arrow-cold)"/>
                <path d="M490 300 H560" class="clear-pipe clear-hot" marker-end="url(#clear-arrow-hot)"/>
                <path d="M490 380 H560" class="clear-pipe clear-cold" marker-end="url(#clear-arrow-cold)"/>
                <path d="M720 300 H780 V300 H900" class="clear-pipe clear-hot" marker-end="url(#clear-arrow-hot)"/>
                <path d="M900 425 H760 V390 H720" class="clear-pipe clear-cold" marker-end="url(#clear-arrow-cold)"/>
                <path d="M490 220 H520 V100 H560" class="clear-pipe clear-dhw"/>
                <path d="M490 250 H540 V160 H560" class="clear-pipe clear-dhw"/>

                <rect x="40" y="170" width="200" height="240" rx="10" class="clear-box"/>
                <text x="140" y="205" text-anchor="middle" class="clear-title">AUSSENEINHEIT</text>
                <text x="140" y="228" text-anchor="middle" class="clear-label">{escape(snapshot.model)}</text>
                <circle cx="140" cy="285" r="34" fill="none" stroke="{'#a83b36' if compressor_active else '#b9c2cc'}" stroke-width="8"/>
                <path d="M140 251 L151 285 L140 319 L129 285 Z" fill="{'#a83b36' if compressor_active else '#b9c2cc'}"/>
                <text x="140" y="345" text-anchor="middle" class="clear-state">Verdichter {"aktiv" if compressor_active else "aus / bereit"}</text>
                <text x="95" y="375" text-anchor="middle" class="clear-label">LÜFTER 1</text>
                <text x="95" y="395" text-anchor="middle" class="clear-value">{escape(value("Außenlüfter 1"))}</text>
                <text x="185" y="375" text-anchor="middle" class="clear-label">LÜFTER 2</text>
                <text x="185" y="395" text-anchor="middle" class="clear-value">{escape(value("Außenlüfter 2"))}</text>

                <rect x="290" y="190" width="200" height="220" rx="10" class="clear-box"/>
                <text x="390" y="225" text-anchor="middle" class="clear-title">INNENEINHEIT</text>
                <circle cx="350" cy="285" r="25" class="clear-sensor"/>
                <path d="M337 285 Q350 266 363 285 Q350 304 337 285" fill="none" stroke="#17202a" stroke-width="3"/>
                <text x="350" y="330" text-anchor="middle" class="clear-state">Pumpe {escape(value("Inneneinheit Pumpe"))}</text>
                <path d="M430 255 L418 280 H428 L421 306 L445 273 H433 Z" fill="{'#c98b4a' if rod_ready else '#b9c2cc'}"/>
                <text x="430" y="335" text-anchor="middle" class="clear-label">HEIZSTAB</text>
                <text x="430" y="353" text-anchor="middle" class="clear-state">{"bereit / heizt nicht" if rod_ready else "gesperrt"}</text>

                <rect x="560" y="250" width="160" height="180" rx="10" class="clear-buffer"/>
                <text x="640" y="285" text-anchor="middle" class="clear-title">PUFFERSPEICHER</text>
                <path d="M585 345 C680 315 680 375 585 355 C680 335 680 395 585 375" fill="none" stroke="#f7fafc" stroke-width="6" stroke-linecap="round"/>
                <text x="640" y="410" text-anchor="middle" class="clear-value">{escape(value("Pufferspeicher"))}</text>
                <text x="640" y="427" text-anchor="middle" class="clear-state">Messwert {escape(feature_time("heating.bufferCylinder.sensors.temperature.main"))}</text>

                <rect x="560" y="40" width="160" height="180" rx="10" class="clear-buffer"/>
                <path d="M585 135 C680 105 680 165 585 145 C680 125 680 185 585 165" fill="none" stroke="#f7fafc" stroke-width="6" stroke-linecap="round"/>
                <text x="640" y="75" text-anchor="middle" class="clear-title" style="font-size:12px">WARMWASSER</text>
                <text x="640" y="94" text-anchor="middle" class="clear-title" style="font-size:12px">SPEICHER</text>
                <text x="640" y="195" text-anchor="middle" class="clear-value">{escape(value("Warmwasser"))}</text>
                <circle cx="780" cy="120" r="18" fill="#fff7ed" stroke="#c98b4a" stroke-width="3"/>
                <path d="M772 120 Q780 110 788 120 Q780 130 772 120" fill="none" stroke="#c98b4a" stroke-width="2"/>
                <path d="M720 80 H780 V180 H720" class="clear-pipe clear-dhw"/>
                <text x="780" y="215" text-anchor="middle" class="clear-label" style="font-size:10px">WARMWASSER-ZIRKULATION</text>
                <text x="780" y="232" text-anchor="middle" class="clear-state">{escape(value("Warmwasser-Zirkulation"))}</text>

                <circle cx="780" cy="300" r="25" class="clear-sensor"/>
                <path d="M767 300 Q780 281 793 300 Q780 319 767 300" fill="none" stroke="#17202a" stroke-width="3"/>
                <text x="780" y="345" text-anchor="middle" class="clear-label">HEIZKREISPUMPE</text>
                <text x="780" y="364" text-anchor="middle" class="clear-value">{escape(value("Heizkreis 1 Pumpe"))}</text>

                <path d="M900 300 H1080 V325 H900 V350 H1080 V375 H900 V400 H1080 V425 H900" class="clear-floor clear-floor-hot"/>
                <path d="M900 425 H1080" class="clear-floor clear-floor-cold"/>
                <text x="990" y="270" text-anchor="middle" class="clear-title" style="font-size:12px">FUSSBODENHEIZUNG</text>
                <text x="990" y="288" text-anchor="middle" class="clear-value">Vorlauf {escape(value("Heizkreis 1 Vorlauf"))}</text>
                <text x="990" y="305" text-anchor="middle" class="clear-state">Messwert {escape(feature_time("heating.circuits.0.sensors.temperature.supply"))}</text>
                <text x="1100" y="450" text-anchor="middle" class="clear-label">HEIZKREIS-RÜCKLAUF</text>
                <text x="1100" y="470" text-anchor="middle" class="clear-state">kein separater Viessmann-Sensor</text>
            </svg>
        </div>
        '''
    render_embedded_html(schema, 620)


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
            .component-hot {{ stroke: #a83b36; }} .component-cold {{ stroke: #385b85; }}
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
