"""Downloadable usage and alert reports (FR-26)."""
import io
import pandas as pd
import streamlit as st

import ui


def _xlsx(df):
    buf = io.BytesIO()
    out = df.copy()
    for c in out.columns:                      # Excel cannot store timezone-aware or odd dtypes
        if str(out[c].dtype).startswith("datetime"):
            out[c] = out[c].dt.strftime("%Y-%m-%d %H:%M:%S")
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        out.to_excel(w, index=False, sheet_name="report")
    return buf.getvalue()


def render(ctx):
    ui.page_header("Reports", "Download usage and alert reports for the date range chosen in the sidebar.")
    p = ctx.provider
    caps = p.get_capabilities()
    daily = caps["granularity"] == "daily"
    kind = st.selectbox("Report type", ["Usage readings", "Alerts", "Theft events", "Relay actions"])
    scope = st.radio("Devices", ["Selected device", "All my devices"], horizontal=True)
    ids = [ctx.device_id] if scope == "Selected device" else ctx.device_ids

    if kind == "Usage readings":
        freq = "1D" if daily else st.selectbox("Resolution", ["5min", "15min", "1h"], index=1)
        frames = []
        for d in ids:
            r = p.get_readings(d, ctx.start, ctx.end, freq)
            if len(r):
                r.insert(0, "device_id", d)
                frames.append(r)
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    elif kind == "Alerts":
        df = p.get_alerts(ids, ctx.start, ctx.end)
    elif kind == "Theft events":
        df = p.get_theft_events(ids, ctx.start, ctx.end)
    else:
        df = p.get_relay_log(ids, ctx.start, ctx.end)

    if df.empty:
        return ui.empty_state("No data for this selection. Try a wider date range.")

    if kind == "Usage readings":
        k = st.columns(4)
        with k[0]:
            ui.metric_card("Rows", f"{len(df):,}")
        if daily:
            with k[1]:
                ui.metric_card("Average per day", f"{df['kwh'].mean():.2f}", "kWh")
            with k[2]:
                ui.metric_card("Highest day", f"{df['kwh'].max():.2f}", "kWh")
            with k[3]:
                ui.metric_card("Energy in range", f"{df['kwh'].sum():.1f}", "kWh")
        else:
            with k[1]:
                ui.metric_card("Average power", f"{df['power'].mean():.0f}", "W")
            with k[2]:
                ui.metric_card("Peak power", f"{df['power'].max():.0f}", "W")
            with k[3]:
                hrs = {"5min": 5, "15min": 15, "1h": 60}[freq] / 60
                ui.metric_card("Energy in range", f"{df['power'].sum() * hrs / 1000:.1f}", "kWh")
        st.write("")
    st.dataframe(df, width="stretch", hide_index=True, height=360)
    name = f"voltiq_{kind.lower().replace(' ', '_')}_{ctx.start:%Y%m%d}_{ctx.end:%Y%m%d}"
    a, b = st.columns(2)
    a.download_button("Download CSV", df.to_csv(index=False).encode(), name + ".csv", "text/csv", width="stretch")
    b.download_button("Download Excel", _xlsx(df), name + ".xlsx",
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
