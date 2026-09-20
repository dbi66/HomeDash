from __future__ import annotations

import streamlit as st


APP_THEME = """
<style>
    .stApp {
        background: #f3f7fb;
    }

    [data-testid="stAppViewContainer"] .main .block-container {
        padding-top: 0.75rem;
        padding-bottom: 0.75rem;
    }

    [data-testid="stVerticalBlock"] {
        gap: 0.05rem;
    }

    [data-testid="stElementContainer"] {
        margin-bottom: 0 !important;
        padding-bottom: 0 !important;
    }

    [data-testid="stHorizontalBlock"] {
        gap: 0.75rem;
    }

    .stApp h3,
    .stApp [data-testid="stMetricLabel"],
    .stApp [data-testid="stMetricValue"],
    .stApp [data-testid="stCaptionContainer"] {
        color: #102a43 !important;
    }

    .stApp [data-testid="stMetricLabel"] {
        font-size: 0.78rem;
        font-weight: 700;
    }

    .stApp [data-testid="stMetricValue"] {
        font-size: 1.35rem;
        font-weight: 800;
    }

    .stApp h3 {
        margin-top: 0.35rem !important;
        margin-bottom: 0.15rem !important;
    }

    .stApp h1,
    .stApp h2 {
        margin-top: 0.35rem !important;
        margin-bottom: 0.15rem !important;
    }

    .weather-grid {
        display: grid;
        gap: 0.7rem;
        grid-template-columns: repeat(7, minmax(120px, 1fr));
        margin: 0.5rem 0 1rem;
        overflow-x: auto;
    }

    .weather-card {
        background: #ffffff;
        border: 1px solid #d9e2ec;
        border-radius: 10px;
        min-width: 120px;
        padding: 0.8rem 0.7rem;
    }

    .weather-card__day { color: #243b53; font-size: 0.85rem; font-weight: 800; }
    .weather-card__icon { color: #1d4ed8 !important; font-size: 2rem; line-height: 1.1; margin: 0.45rem 0; }
    .weather-card__condition { color: #627d98; font-size: 0.78rem; min-height: 2.1rem; }
    .weather-card__temps { color: #102a43; font-size: 1rem; font-weight: 800; margin-top: 0.55rem; }
    .weather-card__meta { color: #627d98; font-size: 0.72rem; line-height: 1.5; margin-top: 0.35rem; }

    .home-hero {
        background: linear-gradient(135deg, #102a43 0%, #243b53 58%, #486581 100%);
        border-radius: 12px;
        color: #ffffff;
        margin: 0.15rem 0 0.55rem;
        padding: 0.85rem 1rem;
    }

    .home-hero__eyebrow { color: #bcccdc; font-size: 0.7rem; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }
    .home-hero__title { font-size: 1.45rem; font-weight: 800; margin-top: 0.15rem; }
    .home-hero__meta { color: #d9e2ec; font-size: 0.8rem; margin-top: 0.2rem; }
    .home-tile-grid { display: grid; gap: 0.55rem; grid-template-columns: repeat(2, minmax(0, 1fr)); margin: 0.25rem 0 0.6rem; }
    .home-tile { background: #ffffff; border: 1px solid #d9e2ec; border-radius: 10px; min-height: 118px; padding: 0.7rem 0.8rem; }
    .home-tile__title { color: #102a43; font-size: 0.92rem; font-weight: 800; }
    .home-tile__subtitle { color: #627d98; font-size: 0.72rem; margin-top: 0.1rem; }
    .home-tile__value { color: #102a43; font-size: 1.3rem; font-weight: 800; margin-top: 0.4rem; }
    .home-tile__detail { color: #486581; font-size: 0.76rem; line-height: 1.45; margin-top: 0.15rem; }

    .stButton > button {
        white-space: normal !important;
        line-height: 1.3 !important;
        text-align: left !important;
        padding: 0.65rem 0.7rem !important;
        word-break: break-word !important;
        overflow-wrap: anywhere !important;
    }

    .home-tile-grid [data-testid="stButton"] button {
        border-color: #9fb3c8;
        color: #102a43;
        font-size: 0.78rem;
        min-height: 34px !important;
        margin-top: 0.35rem;
    }

    div[data-testid="stAlert"] {
        border-radius: 10px;
        padding: 0.55rem 0.75rem !important;
        margin: 0.25rem 0 0.5rem !important;
    }

    div[data-testid="stAlert"] p {
        margin: 0;
        line-height: 1.35;
    }

    @media (max-width: 700px) {
        .home-tile-grid { grid-template-columns: 1fr; }
        .home-hero__title { font-size: 1.2rem; }
        .home-tile { min-height: 92px; }
        .stButton > button {
            font-size: 0.8rem !important;
            padding: 0.55rem 0.6rem !important;
            word-break: break-word !important;
            overflow-wrap: anywhere !important;
        }
        div[data-testid="stAlert"] {
            padding: 0.45rem 0.6rem !important;
        }
    }

    @media (max-width: 800px) {
        .weather-grid { grid-template-columns: repeat(7, minmax(128px, 1fr)); }
    }

    .dashboard-header {
        padding: 0.35rem 0 0.5rem;
    }

    .dashboard-header h1 {
        color: #102a43;
        font-size: 1.8rem;
        letter-spacing: 0;
        margin-bottom: 0.18rem;
    }

    [class*="st-key-refresh-button"] button {
        background: #ffffff;
        border: 1px solid #bcccdc;
        border-radius: 8px;
        color: #102a43;
        min-height: 42px !important;
        padding: 0.45rem 0.8rem !important;
    }

    [class*="st-key-refresh-button"] button p {
        font-size: 0.8rem;
        font-weight: 700;
    }

    .dashboard-header p {
        color: #627d98;
        margin: 0;
    }

    .room-grid {
        display: grid;
        gap: 1rem;
        grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
        margin: 1.25rem 0 1.75rem;
    }

    .level-heading {
        color: #102a43;
        font-size: 1.35rem;
        font-weight: 750;
        margin: 0.5rem 0 0.25rem;
    }

    .heat-map-section {
        background: #f7fafc;
        border: 1px solid #d9e2ec;
        border-radius: 8px;
        margin: 0.45rem 0;
        padding: 0.65rem;
    }

    .heat-map-section__title {
        color: #243b53;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.04em;
        margin-bottom: 0.45rem;
        text-transform: uppercase;
    }

    .heat-pump-schema-wrap {
        background: #f7fafc;
        border: 1px solid #d9e2ec;
        border-radius: 8px;
        overflow-x: auto;
        padding: 0.5rem;
    }

    .heat-pump-schema {
        display: block;
        min-width: 760px;
        width: 100%;
    }

    .schema-pipe {
        fill: none;
        stroke-linecap: round;
        stroke-linejoin: round;
        stroke-width: 8;
    }

    .schema-hot { stroke: #a83b36; }
    .schema-cold { stroke: #385b85; }
    .schema-device, .schema-tank, .schema-dhw { fill: #fff; stroke: #17202a; stroke-width: 2; }
    .schema-tank { fill: #e7edf3; }
    .schema-dhw { fill: #fff7ed; }
    .schema-tank-line { stroke: #9aa5b1; stroke-width: 2; }
    .schema-pump { fill: #fff; stroke: #17202a; stroke-width: 3; }
    .schema-value { fill: #fff; stroke: #7b8794; stroke-width: 1.5; }
    .schema-title, .schema-subtitle, .schema-label, .schema-reading, .schema-state, .schema-sensor, .schema-value-text { font-family: sans-serif; }
    .schema-title { fill: #17202a; font-size: 14px; font-weight: 800; letter-spacing: 1px; }
    .schema-subtitle, .schema-label { fill: #52606d; font-size: 12px; }
    .schema-reading, .schema-value-text { fill: #17202a; font-size: 15px; font-weight: 700; }
    .schema-state { fill: #7b8794; font-size: 12px; }
    .schema-sensor { fill: #17202a; font-size: 17px; font-weight: 800; }

    .heat-map-grid {
        display: grid;
        gap: 0.45rem;
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .heat-map-card {
        background: #ffffff;
        border-left: 4px solid #9fb3c8;
        border-radius: 6px;
        box-shadow: 0 2px 8px rgba(16, 42, 67, 0.06);
        min-height: 76px;
        padding: 0.55rem 0.65rem;
    }

    .heat-map-card.active {
        border-left-color: #2f855a;
    }

    .heat-map-card.sensor {
        border-left-color: #3182ce;
    }

    .heat-map-card__name {
        color: #486581;
        font-size: 0.72rem;
        font-weight: 700;
    }

    .heat-map-card__value {
        color: #102a43;
        font-size: 1rem;
        font-weight: 800;
        margin-top: 0.25rem;
    }

    .heat-map-card__state {
        color: #627d98;
        font-size: 0.68rem;
        margin-top: 0.15rem;
    }

    .room-card {
        border: 1px solid rgba(16, 42, 67, 0.12);
        border-radius: 10px;
        box-shadow: 0 8px 20px rgba(16, 42, 67, 0.08);
        min-height: 154px;
        padding: 0.9rem;
    }

    .room-card__top,
    .room-card__meta,
    .room-card__reading {
        align-items: center;
        display: flex;
        justify-content: space-between;
    }

    .room-card__name {
        color: #102a43;
        font-size: 1.05rem;
        font-weight: 700;
        overflow-wrap: anywhere;
    }

    .room-card__status {
        color: #486581;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }

    .room-card__reading {
        align-items: baseline;
        margin: 1.25rem 0 1rem;
    }

    .room-card__temperature {
        color: #102a43;
        font-size: 2.35rem;
        font-weight: 750;
        line-height: 1;
    }

    .room-card__target {
        color: #486581;
        font-size: 0.85rem;
    }

    .room-card__meta {
        border-top: 1px solid rgba(16, 42, 67, 0.12);
        color: #334e68;
        font-size: 0.84rem;
        padding-top: 0.75rem;
    }

    .room-card__meta strong {
        color: #102a43;
    }

    @media (max-width: 640px) {
        .block-container {
            padding: 1rem 0.75rem 2rem;
        }

        .dashboard-header h1 {
            font-size: 1.6rem;
        }

        .room-grid {
            gap: 0.5rem;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            margin: 0.75rem 0 1.25rem;
        }

        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap;
            gap: 0.5rem;
            max-width: calc(100vw - 1.5rem) !important;
            width: calc(100vw - 1.5rem) !important;
        }

        [data-testid="stColumn"] {
            flex: 0 0 calc(50% - 0.25rem);
            min-width: 0;
            width: calc(50% - 0.25rem) !important;
        }

        [data-testid="stHorizontalBlock"]:has(.dashboard-header) {
            flex-wrap: wrap;
        }

        [data-testid="stHorizontalBlock"]:has(.dashboard-header) [data-testid="stColumn"] {
            flex: 0 0 100%;
            width: 100% !important;
        }

        [data-testid="stHorizontalBlock"]:has([data-testid="stVegaLiteChart"]) [data-testid="stColumn"] {
            flex: 0 0 100%;
            width: 100% !important;
        }

        .level-heading {
            font-size: 1.1rem;
            margin-top: 1.2rem;
        }

        .room-card {
            border-radius: 8px;
            min-height: 126px;
            padding: 0.65rem;
        }

        .room-card__name {
            font-size: 0.78rem;
        }

        .room-card__status {
            font-size: 0.55rem;
        }

        .room-card__reading {
            margin: 0.8rem 0 0.65rem;
        }

        .room-card__temperature {
            font-size: 1.35rem;
        }

        .room-card__target {
            font-size: 0.62rem;
        }

        .room-card__meta {
            display: grid;
            font-size: 0.62rem;
            gap: 0.25rem;
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .room-card__meta span {
            white-space: nowrap;
        }

        .stButton button[kind="secondary"] {
            min-height: 96px;
            padding: 0.65rem;
        }

        [class*="st-key-overview-room-"] button p:first-child,
        [class*="st-key-room-tile-"] button p:first-child {
            font-size: 0.72rem;
            overflow-wrap: anywhere;
        }

        [class*="st-key-overview-room-"] button p:nth-child(2),
        [class*="st-key-room-tile-"] button p:nth-child(2) {
            font-size: 0.62rem;
            overflow-wrap: anywhere;
        }

        [class*="st-key-overview-room-"] button > div,
        [class*="st-key-room-tile-"] button > div,
        [class*="st-key-overview-room-"] button p,
        [class*="st-key-room-tile-"] button p {
            min-width: 0;
            white-space: normal;
        }
    }

        .stButton button[kind="secondary"] {
            background: #dbeafe;
            border: 1px solid rgba(16, 42, 67, 0.12);
            border-radius: 10px;
            color: #102a43;
            min-height: 96px;
            text-align: left;
            white-space: pre-wrap;
        }

        .stButton button[kind="secondary"] p {
            font-size: 0.78rem;
            line-height: 1.35;
        }

            .device-tree {
                background: #eef5fb;
                border: 1px solid #c9d8e6;
                border-radius: 10px;
                margin-top: 0.75rem;
                padding: 1rem;
            }

            .device-tree__root {
                align-items: center;
                background: #102a43;
                border-radius: 8px;
                color: #ffffff;
                display: flex;
                font-weight: 700;
                gap: 0.6rem;
                padding: 0.7rem 0.85rem;
            }

            .device-tree__branch {
                border-left: 2px solid #9fb3c8;
                margin: 0.5rem 0 0 0.9rem;
                padding-left: 1rem;
            }

            .device-node {
                background: #ffffff;
                border: 1px solid #d9e2ec;
                border-radius: 8px;
                margin: 0.55rem 0;
                padding: 0.7rem;
            }

            .device-node__title {
                color: #102a43;
                font-size: 0.9rem;
                font-weight: 700;
            }

            .device-node__model {
                color: #627d98;
                font-size: 0.75rem;
                margin-left: 0.35rem;
            }

            .channel-chip {
                background: #dbeafe;
                border-radius: 999px;
                color: #243b53;
                display: inline-block;
                font-size: 0.7rem;
                margin: 0.45rem 0.35rem 0 0;
                padding: 0.25rem 0.5rem;
            }

            [class*="st-key-settings-button"] button p {
                font-size: 1.45rem;
                line-height: 1;
            }

            [class*="st-key-overview-room-"] button p:first-child,
            [class*="st-key-room-tile-"] button p:first-child {
                color: #102a43;
                font-size: 0.95rem;
                font-weight: 800;
                line-height: 1.2;
            }

            [class*="st-key-overview-room-"] button p:nth-child(2),
            [class*="st-key-room-tile-"] button p:nth-child(2) {
                color: #486581;
                font-size: 0.72rem;
                font-weight: 500;
                line-height: 1.25;
            }

            [class*="st-key-overview-room-"] button > div,
            [class*="st-key-room-tile-"] button > div {
                display: block !important;
                width: 100%;
            }

            [class*="st-key-overview-room-"] button p,
            [class*="st-key-room-tile-"] button p {
                display: block !important;
                margin: 0;
                width: 100%;
            }

            [class*="st-key-function-navigation"] {
                min-width: 190px;
            }

            [data-testid="stCheckbox"] label p {
                color: #334e68 !important;
                font-size: 0.78rem;
                font-weight: 700;
            }
</style>
"""


def apply_app_theme() -> None:
    st.markdown(APP_THEME, unsafe_allow_html=True)
