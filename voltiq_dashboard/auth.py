"""Login and roles (FR-27). Passwords are stored only as salted PBKDF2 hashes.

Demo users only - replace USERS with a database table in a real deployment.
"""
import hashlib
import hmac
import streamlit as st

from config import APP_TITLE, APP_SUBTITLE


def hash_password(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 100_000).hex()


USERS = {
    "admin": {"name": "Utility Admin", "role": "administrator",
              "salt": "a1b2c3d4e5f60718",
              "hash": "744306edc1d809de02270ff8b2747a5f5966e9b9b83893ce8329f6d9afd494a4"},
    "consumer1": {"name": "Consumer One", "role": "consumer",
                  "salt": "0f1e2d3c4b5a6978",
                  "hash": "3aa66e96d588158554284170041db84efb9b46cd2e5d4092c48b55b9e78b3019"},
    "consumer2": {"name": "Consumer Two", "role": "consumer",
                  "salt": "9988776655443322",
                  "hash": "39aec53ed9afd23959d1ef0457b975033fecfb41f1103d59d7b11f8deb4cf9fd"},
}

DEMO_LOGINS = [("admin", "admin123", "Administrator - all devices, restore load, thresholds"),
               ("consumer1", "consumer123", "Consumer - owns meter_01 and meter_03 (theft demo)"),
               ("consumer2", "consumer123", "Consumer - owns meter_02, meter_04, meter_05")]


def authenticate(username: str, password: str):
    u = USERS.get((username or "").strip().lower())
    if not u:
        return None
    if hmac.compare_digest(hash_password(password or "", u["salt"]), u["hash"]):
        return {"username": username.strip().lower(), "name": u["name"], "role": u["role"]}
    return None


def is_logged_in() -> bool:
    return st.session_state.get("user") is not None


def current_user():
    return st.session_state.get("user")


def is_admin() -> bool:
    u = current_user()
    return bool(u and u["role"] == "administrator")


def logout():
    for k in list(st.session_state.keys()):
        del st.session_state[k]


def user_options():
    """Usernames that can own devices (used by the device registration form)."""
    return [k for k, v in USERS.items() if v["role"] == "consumer"]


def login_screen():
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown(f"<h1 style='text-align:center;margin-bottom:0'>⚡ {APP_TITLE}</h1>"
                    f"<p style='text-align:center;color:#666'>{APP_SUBTITLE}</p>", unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            go = st.form_submit_button("Log in", width="stretch", type="primary")
        if go:
            user = authenticate(username, password)
            if user:
                st.session_state["user"] = user
                st.rerun()
            else:
                st.error("Invalid username or password.")
        with st.expander("Demo credentials", expanded=True):
            for u, p, d in DEMO_LOGINS:
                st.markdown(f"**{u}** / `{p}` - {d}")
