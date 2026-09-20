from __future__ import annotations

import pandas as pd
import streamlit as st


def render_viessmann_inventory(inventory: list[dict[str, object]]) -> None:
    st.caption(f"{len(inventory)} Viessmann-Gerät(e)")
    for device in inventory:
        features = device.get("features", {})
        feature_rows = features.get("data", []) if isinstance(features, dict) else []
        with st.expander(f"{device['model']} | {device['id']} | {'online' if device['online'] else 'offline'}"):
            if not feature_rows:
                st.json(features)
                continue
            rows = [
                {
                    "Feature": feature.get("feature", ""),
                    "Eigenschaften": ", ".join(sorted(feature.get("properties", {}).keys())),
                }
                for feature in feature_rows
                if isinstance(feature, dict)
            ]
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            else:
                st.json(features)
