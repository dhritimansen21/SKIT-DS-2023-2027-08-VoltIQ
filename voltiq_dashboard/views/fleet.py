"""Admin-only fleet overview: all devices, status, theft-risk score, CSV export."""
import streamlit as st

import ui
from config import STATUS_COLORS, RELAY_COLORS


def render(ctx):
    ui.page_header("Fleet Overview", "All registered devices with status and theft-risk score (sortable).")
    df = ctx.provider.get_fleet_overview()
    if df.empty:
        return ui.empty_state("No devices registered yet.")
    k = st.columns(4)
    with k[0]:
        ui.metric_card("Devices", len(df))
    with k[1]:
        ui.metric_card("Online", int((df["status"] != "Offline").sum()), "", "", "#2E7D32")
    with k[2]:
        ui.metric_card("Theft detected", int((df["status"] == "Theft detected").sum()), "", "", "#C62828")
    with k[3]:
        ui.metric_card("Open alerts", int(df["open_alerts"].sum()), "", "", "#F9A825")
    st.write("")
    sty = ui.style_cols(df, {"status": STATUS_COLORS, "relay_state": RELAY_COLORS})
    st.dataframe(sty, width="stretch", hide_index=True,
                 column_config={"theft_risk": st.column_config.ProgressColumn("theft_risk", min_value=0, max_value=1, format="%.2f"),
                                "power_w": st.column_config.NumberColumn("power (W)", format="%d")})
    st.download_button("Export fleet table (CSV)", df.to_csv(index=False).encode(), "voltiq_fleet.csv", "text/csv")
    a, b = st.columns(2)
    a.plotly_chart(ui.bar_chart(df, "device_id", "power_w", "Current power by device", ytitle="W"), width="stretch")
    b.plotly_chart(ui.bar_chart(df, "device_id", "theft_risk", "Theft-risk score by device", "#C62828", ytitle="0 - 1"),
                   width="stretch")
