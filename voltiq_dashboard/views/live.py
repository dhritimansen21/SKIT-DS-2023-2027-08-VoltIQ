"""Live monitoring (FR-22): live V, I, P, energy, status, relay state, auto-refreshing chart."""
import pandas as pd
import streamlit as st

import ui
from config import REFRESH_SECONDS, STATUS_COLORS


def _render_daily(ctx, caps):
    """Daily-kWh data (e.g. the SGCC dataset): no voltage/current and no second-by-second refresh."""
    p, dev = ctx.provider, ctx.device_id
    ui.page_header("Latest Consumption", f"Device {dev} - daily readings, data replayed up to {caps['data_end']:%d %b %Y}")
    st.info("The dataset has one kWh value per day, so voltage, current and live refresh are not available. "
            "The cards show the most recent days in the data.")
    window = st.radio("Chart window", ["30 days", "90 days", "180 days", "1 year"], index=1, horizontal=True)
    days = {"30 days": 30, "90 days": 90, "180 days": 180, "1 year": 365}[window]
    now = caps["now"]
    latest, status, relay = p.get_latest_reading(dev), p.get_device_status(dev), p.get_relay_state(dev)
    hist = p.get_readings(dev, now - pd.Timedelta(days=days), now)
    if not latest["connected"]:
        st.warning(f"No reading for several days. Last reading: {latest['timestamp']:%d %b %Y}.")
    if relay["state"] == "OPEN":
        st.error(f"Load disconnected since {relay['since']:%d %b %Y} (simulated on replayed data). "
                 "An administrator must review the event and restore the load.")
    last7 = hist["kwh"].tail(7).mean()
    exp = latest["expected_kwh"]
    dev_pct = (latest["kwh"] - exp) / exp * 100 if exp and exp == exp and exp > 0 else float("nan")
    c = st.columns(5)
    with c[0]:
        ui.status_card(status, f"Theft probability {latest['theft_prob']:.2f}")
    with c[1]:
        ui.metric_card("Latest day", f"{latest['kwh']:.2f}", "kWh", f"{latest['timestamp']:%d %b %Y}")
    with c[2]:
        ui.metric_card("7-day average", f"{last7:.2f}", "kWh/day", "recent level")
    with c[3]:
        ui.metric_card("Expected", "-" if exp != exp else f"{exp:.2f}", "kWh", "model expectation for that day")
    with c[4]:
        ui.metric_card("Deviation", "-" if dev_pct != dev_pct else f"{dev_pct:+.0f}", "%", "measured vs expected",
                       "#C62828" if dev_pct == dev_pct and abs(dev_pct) > 40 else "#1F5FBF")
    st.write("")
    c = st.columns(4)
    with c[0]:
        ui.metric_card("Anomaly score", f"{latest['anomaly_score']:.2f}", "", "0 = normal, 1 = very unusual")
    with c[1]:
        ui.metric_card("Missing days", int(hist["kwh"].tail(30).isna().sum()), "", "in the last 30 days")
    with c[2]:
        st.markdown(f"<div class='vq-card' style='--c:{'#C62828' if relay['state'] == 'OPEN' else '#2E7D32'}'>"
                    f"<div class='lbl'>Relay state</div><div style='margin:6px 0'>{ui.relay_chip(relay['state'])}</div>"
                    f"<div class='sub'>{'Load cut off' if relay['state'] == 'OPEN' else 'Load connected'}</div></div>",
                    unsafe_allow_html=True)
    with c[3]:
        ui.metric_card("Total energy", f"{latest['energy']:.0f}", "kWh", "since 1 Jan 2014")
    st.write("")
    if hist.empty:
        return ui.empty_state("No readings in this window.")
    st.plotly_chart(ui.power_chart(hist, f"Daily consumption - last {window}", value_col="kwh",
                                   expected_col="expected_kwh", ytitle=caps["unit_label"]), width="stretch")


def render(ctx):
    caps = ctx.provider.get_capabilities()
    if caps["granularity"] == "daily":
        return _render_daily(ctx, caps)
    ui.page_header("Live Monitoring", f"Device {ctx.device_id} - values refresh automatically every {REFRESH_SECONDS} s")
    c1, c2 = st.columns([3, 1])
    window = c1.radio("Chart window", ["30 min", "1 h", "3 h", "6 h"], index=1, horizontal=True)
    auto = c2.toggle(f"Auto-refresh ({REFRESH_SECONDS} s)", value=True)
    minutes = {"30 min": 30, "1 h": 60, "3 h": 180, "6 h": 360}[window]

    def body():
        p, dev = ctx.provider, ctx.device_id
        now = pd.Timestamp.now()
        latest = p.get_latest_reading(dev)
        status = p.get_device_status(dev)
        hist = p.get_readings(dev, now - pd.Timedelta(minutes=minutes), now, "1min")
        prev = hist.iloc[-2] if len(hist) > 1 else None
        relay = p.get_relay_state(dev)

        if not latest["connected"]:
            st.warning(f"Device offline. Last reading at {latest['timestamp']:%d %b %H:%M:%S}. "
                       "The unit keeps buffering readings on its microSD card and will re-send them when Wi-Fi returns.")
        if relay["state"] == "OPEN":
            st.error(f"Load disconnected since {relay['since']:%d %b %H:%M}. {relay['reason']}. "
                     "An administrator must review the event and restore the load.")

        def dlt(key, fmt):
            return f"{latest[key] - prev[key]:+{fmt}} vs 1 min ago" if prev is not None and latest["connected"] else ""

        cols = st.columns(5)
        with cols[0]:
            ui.status_card(status, f"Anomaly score {latest['anomaly_score']:.2f}")
        with cols[1]:
            ui.metric_card("Voltage", f"{latest['voltage']:.1f}", "V", dlt("voltage", ".1f"))
        with cols[2]:
            ui.metric_card("Current", f"{latest['current']:.2f}", "A", dlt("current", ".2f"))
        with cols[3]:
            ui.metric_card("Power", f"{latest['power']:.0f}", "W", f"{latest['power'] / 1000:.2f} kW")
        with cols[4]:
            today = p.get_readings(dev, now.normalize(), now, "15min")
            e_today = today["power"].sum() * 0.25 / 1000 if len(today) else 0
            ui.metric_card("Energy", f"{latest['energy']:.1f}", "kWh", f"Today: {e_today:.2f} kWh")

        st.write("")
        c = st.columns(4)
        with c[0]:
            ui.metric_card("Connection", "Online" if latest["connected"] else "Offline", "",
                           "Wi-Fi link to server", "#2E7D32" if latest["connected"] else "#757575")
        with c[1]:
            ui.metric_card("Last reading", f"{latest['timestamp']:%H:%M:%S}", "", f"{latest['timestamp']:%d %b %Y}")
        with c[2]:
            st.markdown(f"<div class='vq-card' style='--c:{'#C62828' if relay['state'] == 'OPEN' else '#2E7D32'}'>"
                        f"<div class='lbl'>Relay state</div><div style='margin:6px 0'>{ui.relay_chip(relay['state'])}</div>"
                        f"<div class='sub'>{'Load cut off' if relay['state'] == 'OPEN' else 'Load connected'}</div></div>",
                        unsafe_allow_html=True)
        with c[3]:
            ui.metric_card("Data sync", "Synced" if latest["connected"] else "Pending", "", latest["sync_status"])

        st.write("")
        if latest["connected"]:
            row = pd.DataFrame([{**{k: latest[k] for k in hist.columns if k in latest}}])
            hist = pd.concat([hist, row], ignore_index=True)
        if hist.empty:
            ui.empty_state("No readings in this window yet.")
        else:
            st.plotly_chart(ui.power_chart(hist, f"Live power - last {window}"), width="stretch")
            with st.expander("Voltage and current"):
                a, b = st.columns(2)
                a.line_chart(hist.set_index("timestamp")["voltage"], height=220)
                b.line_chart(hist.set_index("timestamp")["current"], height=220)

    frag = getattr(st, "fragment", None)
    if frag:
        frag(run_every=REFRESH_SECONDS if auto else None)(body)()
    else:
        body()
