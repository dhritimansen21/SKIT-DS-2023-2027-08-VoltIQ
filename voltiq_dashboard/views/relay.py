"""Relay control (FR-18..FR-21): status, restore (admin only, with confirmation) and action log."""
import pandas as pd
import streamlit as st

import ui


def render(ctx):
    ui.page_header("Relay Control", "A relay opens only after theft is confirmed. Only an administrator can restore the load.")
    p = ctx.provider
    rows = []
    for dev in ctx.device_ids:
        s = p.get_relay_state(dev)
        rows.append(dict(device=dev, state=s["state"], since=s["since"], reason=s["reason"]))
    cols = st.columns(min(len(rows), 4) or 1)
    for i, r in enumerate(rows):
        with cols[i % len(cols)]:
            st.markdown(f"<div class='vq-card' style='--c:{'#C62828' if r['state'] == 'OPEN' else '#2E7D32'}'>"
                        f"<div class='lbl'>{r['device']}</div><div style='margin:6px 0'>{ui.relay_chip(r['state'])}</div>"
                        f"<div class='sub'>{('Since ' + r['since'].strftime('%d %b %H:%M')) if r['since'] is not None else 'Load connected'}</div></div>",
                        unsafe_allow_html=True)
    st.write("")

    st.subheader("Restore load")
    open_devs = [r["device"] for r in rows if r["state"] == "OPEN"]
    if not ctx.is_admin:
        st.info("Only an administrator can restore a disconnected load. Please contact your utility.")
    elif not open_devs:
        st.success("All relays are closed. Nothing to restore.")
    else:
        dev = st.selectbox("Device to restore", open_devs)
        reason = st.text_input("Reason / review note", "Event reviewed on site; load restored")
        sure = st.checkbox("I have reviewed the theft event and confirm that the load can be restored.")
        if st.button("Restore load", type="primary", disabled=not sure):
            ok, msg = p.restore_load(dev, ctx.user["username"], reason)
            st.toast(msg, icon="✅" if ok else "⚠️")
            st.rerun()

    if ctx.is_admin and p.get_capabilities().get("can_simulate", False):
        with st.expander("Demo tool: simulate a theft event"):
            st.caption("Creates a confirmed theft event, raises an alert and cuts the load (mock data only).")
            closed = [r["device"] for r in rows if r["state"] == "CLOSED"]
            if closed:
                d2 = st.selectbox("Device", closed, key="sim_dev")
                if st.button("Simulate theft"):
                    ok, msg = p.simulate_theft(d2, ctx.user["username"])
                    st.toast(msg, icon="✅" if ok else "⚠️")
                    st.rerun()
            else:
                st.write("All relays are already open.")

    st.subheader("Cut-off and restore log")
    log = p.get_relay_log(ctx.device_ids, ctx.start - pd.Timedelta(days=30), ctx.end)
    if log.empty:
        ui.empty_state("No relay actions recorded.")
    else:
        st.dataframe(ui.style_cols(log, {"action": {"OPEN": "#C62828", "CLOSE": "#2E7D32"}}),
                     width="stretch", hide_index=True)
