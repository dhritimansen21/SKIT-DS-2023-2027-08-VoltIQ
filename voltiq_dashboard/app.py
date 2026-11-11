"""VoltIQ dashboard entry point:  streamlit run app.py"""
from datetime import date, datetime, time, timedelta

import streamlit as st

import auth
import ui
from config import APP_TITLE, APP_SUBTITLE, DATA_MODE, PAGES_ADMIN, PAGES_CONSUMER
from context import Ctx
from data_provider import MockDataProvider
from sample_provider import SampleDataProvider
from views import admin, alerts, fleet, forecast, live, model_info, relay, reports

st.set_page_config(page_title=f"{APP_TITLE} Dashboard", page_icon="⚡", layout="wide")
ui.inject_css()


@st.cache_resource
def get_provider():
    """One provider instance shared by all sessions."""
    return SampleDataProvider() if DATA_MODE == "sample" else MockDataProvider()


ROUTES = {"Live Monitoring": live, "Forecast": forecast, "Alerts & Anomalies": alerts, "Relay Control": relay,
          "Reports": reports, "Model Info": model_info, "Fleet Overview": fleet, "Admin Settings": admin}

if not auth.is_logged_in():
    auth.login_screen()
    st.stop()

user = auth.current_user()
provider = get_provider()
admin_user = user["role"] == "administrator"
devices = provider.get_devices(owner=None if admin_user else user["username"])

with st.sidebar:
    st.markdown(f"## ⚡ {APP_TITLE}")
    st.caption(APP_SUBTITLE)
    st.markdown(f"**{user['name']}**  \n`{user['role']}`")
    if st.button("Log out", width="stretch"):
        auth.logout()
        st.rerun()
    st.divider()
    if devices.empty:
        st.warning("No devices are assigned to your account yet.")
        st.stop()
    device_id = st.selectbox("Device", devices["device_id"],
                             format_func=lambda d: f"{d} - {devices.set_index('device_id').loc[d, 'location']}")
    caps = provider.get_capabilities()
    if caps["granularity"] == "daily":
        last, first = caps["data_end"].date(), caps["data_start"].date()
        rng = st.date_input("Date range", value=(last - timedelta(days=89), last), min_value=first, max_value=last)
    else:
        today = date.today()
        rng = st.date_input("Date range", value=(today - timedelta(days=7), today), max_value=today)
    d0, d1 = (rng[0], rng[1]) if isinstance(rng, (list, tuple)) and len(rng) == 2 else (rng[0] if isinstance(rng, (list, tuple)) else rng,) * 2
    start, end = datetime.combine(d0, time.min), datetime.combine(d1, time.max)
    page = st.radio("View", PAGES_ADMIN if admin_user else PAGES_CONSUMER)
    st.divider()
    st.caption(caps["source"])

ctx = Ctx(provider=provider, user=user, devices=devices, device_id=device_id, start=start, end=end)
ROUTES[page].render(ctx)
