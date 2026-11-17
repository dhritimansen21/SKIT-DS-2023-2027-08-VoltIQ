"""Anomalies, theft events and alerts (FR-24) with acknowledgement (FR-29)."""
import pandas as pd
import streamlit as st

import ui
from config import SEVERITY_COLORS, SEVERITY_ORDER


def render(ctx):
    ui.page_header("Alerts & Anomalies", "Colour-coded by severity. Acknowledge an alert once you have seen it.")
    p = ctx.provider
    caps = p.get_capabilities()
    scope = st.radio("Show", ["Selected device", "All my devices"], horizontal=True)
    ids = [ctx.device_id] if scope == "Selected device" else ctx.device_ids
    alerts = p.get_alerts(ids, ctx.start, ctx.end)

    f1, f2 = st.columns(2)
    sev = f1.multiselect("Severity", SEVERITY_ORDER, default=SEVERITY_ORDER)
    stat = f2.multiselect("Status", ["Open", "Acknowledged"], default=["Open", "Acknowledged"])
    if len(alerts):
        alerts = alerts[alerts["severity"].isin(sev) & alerts["status"].isin(stat)]

    k = st.columns(4)
    with k[0]:
        ui.metric_card("Alerts", len(alerts), "", "in selected range")
    with k[1]:
        ui.metric_card("Open", int((alerts["status"] == "Open").sum()) if len(alerts) else 0, "", "not yet acknowledged", "#F9A825")
    with k[2]:
        ui.metric_card("Critical / high", int(alerts["severity"].isin(["critical", "high"]).sum()) if len(alerts) else 0, "", "", "#C62828")
    with k[3]:
        ui.metric_card("Confirmed theft", int((alerts["event_type"] == "Theft").sum()) if len(alerts) else 0, "", "", "#C62828")

    st.subheader("Alert log")
    if alerts.empty:
        ui.empty_state("No alerts match the current filters and date range.")
    else:
        show = alerts[["alert_id", "created_at", "device_id", "severity", "event_type", "anomaly_score",
                       "theft_probability", "status", "acknowledged_by", "acknowledged_at", "message"]]
        st.dataframe(ui.style_severity(show), width="stretch", hide_index=True)

        openal = alerts[alerts["status"] == "Open"]
        if len(openal):
            st.markdown("**Acknowledge an alert**")
            a, b = st.columns([3, 1])
            pick = a.selectbox("Open alerts", openal["alert_id"],
                               format_func=lambda i: f"{i} - {openal.set_index('alert_id').loc[i, 'device_id']} "
                                                     f"({openal.set_index('alert_id').loc[i, 'severity']})")
            b.write("")
            b.write("")
            if b.button("Acknowledge", type="primary", width="stretch"):
                ok, msg = p.acknowledge_alert(pick, ctx.user["username"])
                st.toast(msg, icon="✅" if ok else "⚠️")
                st.rerun()

    st.subheader("Anomalies on the power curve")
    readings = p.get_readings(ctx.device_id, ctx.start, ctx.end, ui.auto_freq(ctx.start, ctx.end))
    if readings.empty:
        ui.empty_state("No readings in this date range.")
    else:
        st.plotly_chart(ui.power_chart(readings, f"{ctx.device_id} - flagged readings (x)", value_col=caps["value_col"],
                                       expected_col=caps["expected_col"], ytitle=caps["unit_label"]), width="stretch")
        flagged = readings[readings["flagged"]]
        st.caption(f"{len(flagged)} flagged readings out of {len(readings)} "
                   f"(anomaly threshold {p.get_thresholds()['anomaly_threshold']:.2f}).")

    st.subheader("Theft events")
    ev = p.get_theft_events(ids, ctx.start, ctx.end)
    if ev.empty:
        ui.empty_state("No events in this range.")
    else:
        st.dataframe(ev, width="stretch", hide_index=True)
