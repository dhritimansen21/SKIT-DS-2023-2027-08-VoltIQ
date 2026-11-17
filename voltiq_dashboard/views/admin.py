"""Admin settings: device registration/editing (FR-28) and detection thresholds (FR-28)."""
import streamlit as st

import auth
import ui
from config import DEFAULT_THRESHOLDS


def render(ctx):
    ui.page_header("Admin Settings", "Register devices and set detection thresholds.")
    p = ctx.provider
    tab_dev, tab_thr = st.tabs(["Devices", "Detection thresholds"])

    with tab_dev:
        devs = p.get_devices()
        st.dataframe(devs, width="stretch", hide_index=True)
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Register a device")
            with st.form("reg_form", clear_on_submit=True):
                did = st.text_input("Device ID", placeholder="meter_06")
                loc = st.text_input("Location")
                own = st.selectbox("Owner", auth.user_options())
                if st.form_submit_button("Register", type="primary"):
                    ok, msg = p.register_device(did, loc, own)
                    st.toast(msg, icon="✅" if ok else "⚠️")
                    if ok:
                        st.rerun()
        with c2:
            st.subheader("Edit a device")
            if devs.empty:
                ui.empty_state("No devices yet.")
            else:
                sel = st.selectbox("Device", devs["device_id"], key="edit_dev")
                row = devs.set_index("device_id").loc[sel]
                with st.form("edit_form"):
                    loc2 = st.text_input("Location", row["location"])
                    owners = auth.user_options()
                    own2 = st.selectbox("Owner", owners, index=owners.index(row["owner"]) if row["owner"] in owners else 0)
                    act = st.toggle("Active", value=bool(row["active"]))
                    if st.form_submit_button("Save changes"):
                        ok, msg = p.update_device(sel, loc2, own2, act)
                        st.toast(msg, icon="✅" if ok else "⚠️")
                        if ok:
                            st.rerun()

    with tab_thr:
        t = p.get_thresholds()
        st.caption("A theft event is confirmed only when the classifier probability stays above the threshold "
                   "for N consecutive windows (FR-16). One window = 5 minutes.")
        with st.form("thr_form"):
            a = st.slider("Anomaly score threshold", 0.0, 1.0, float(t["anomaly_threshold"]), 0.01,
                          help="Readings with a score above this are flagged as anomalies.")
            tau = st.slider("Theft probability threshold (tau)", 0.5, 0.99, float(t["theft_prob_tau"]), 0.01)
            n = st.number_input("Consecutive windows to confirm theft (N)", 1, 12, int(t["n_windows"]))
            c1, c2 = st.columns(2)
            save = c1.form_submit_button("Save thresholds", type="primary")
            reset = c2.form_submit_button("Reset to defaults")
        if save:
            p.set_thresholds({"anomaly_threshold": a, "theft_prob_tau": tau, "n_windows": int(n)})
            st.success("Thresholds saved.")
        if reset:
            p.set_thresholds(dict(DEFAULT_THRESHOLDS))
            st.success("Thresholds reset to defaults.")
            st.rerun()
