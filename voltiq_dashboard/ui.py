"""Shared UI components: CSS, metric cards, badges, colour-coded tables and Plotly charts."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import SEVERITY_COLORS, STATUS_COLORS, RELAY_COLORS, PRIMARY, ACCENT

CSS = """
<style>
.block-container {padding-top: 2.2rem; padding-bottom: 2rem;}
.vq-card {background:#fff; border:1px solid #E3E8EF; border-left:5px solid var(--c,#1F5FBF);
          border-radius:10px; padding:14px 16px; box-shadow:0 1px 3px rgba(16,24,40,.06); height:100%;}
.vq-card .lbl {font-size:.78rem; color:#667085; text-transform:uppercase; letter-spacing:.04em;}
.vq-card .val {font-size:1.7rem; font-weight:700; color:#101828; line-height:1.25;}
.vq-card .unit {font-size:.95rem; font-weight:500; color:#667085; margin-left:4px;}
.vq-card .sub {font-size:.8rem; color:#667085; margin-top:2px;}
.vq-badge {display:inline-block; padding:4px 12px; border-radius:999px; color:#fff; font-weight:600; font-size:.9rem;}
.vq-chip {display:inline-block; padding:2px 10px; border-radius:6px; color:#fff; font-weight:600; font-size:.8rem;}
.vq-title {display:flex; align-items:center; gap:.6rem; margin-bottom:.2rem;}
@media (prefers-color-scheme: dark) {
  .vq-card {background:#1B2230; border-color:#2F3A4D;}
  .vq-card .val {color:#F2F4F7;}
}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def metric_card(label, value, unit="", sub="", color=PRIMARY):
    st.markdown(f"<div class='vq-card' style='--c:{color}'><div class='lbl'>{label}</div>"
                f"<div class='val'>{value}<span class='unit'>{unit}</span></div>"
                f"<div class='sub'>{sub or '&nbsp;'}</div></div>", unsafe_allow_html=True)


def badge_html(text, color):
    return f"<span class='vq-badge' style='background:{color}'>{text}</span>"


def status_badge(status):
    return badge_html(status, STATUS_COLORS.get(status, "#757575"))


def status_card(status, sub=""):
    color = STATUS_COLORS.get(status, "#757575")
    st.markdown(f"<div class='vq-card' style='--c:{color}'><div class='lbl'>Overall status</div>"
                f"<div style='margin:6px 0'>{badge_html(status, color)}</div>"
                f"<div class='sub'>{sub or '&nbsp;'}</div></div>", unsafe_allow_html=True)


def relay_chip(state):
    return f"<span class='vq-chip' style='background:{RELAY_COLORS.get(state, '#757575')}'>{state}</span>"


def page_header(title, subtitle=""):
    st.markdown(f"<div class='vq-title'><h2 style='margin:0'>{title}</h2></div>", unsafe_allow_html=True)
    if subtitle:
        st.caption(subtitle)


def auto_freq(start, end):
    days = (pd.Timestamp(end) - pd.Timestamp(start)).total_seconds() / 86400
    return "5min" if days <= 1.5 else "15min" if days <= 7 else "1h"


def style_severity(df, col="severity"):
    """Colour-code the severity column of a dataframe (returns a Styler)."""
    def paint(v):
        c = SEVERITY_COLORS.get(str(v).lower())
        return f"background-color:{c}; color:white; font-weight:600" if c else ""
    sty = df.style
    return (sty.map(paint, subset=[col]) if hasattr(sty, "map") else sty.applymap(paint, subset=[col]))


def style_cols(df, mapping):
    """mapping: {column: {value: colour}} -> Styler with coloured cells."""
    def mk(cmap):
        return lambda v: (f"background-color:{cmap[v]}; color:white; font-weight:600" if v in cmap else "")
    sty = df.style
    for col, cmap in mapping.items():
        sty = sty.map(mk(cmap), subset=[col]) if hasattr(sty, "map") else sty.applymap(mk(cmap), subset=[col])
    return sty


def _layout(fig, title="", height=380, ytitle="Power (W)"):
    fig.update_layout(title=dict(text=title, x=0.01), height=height, margin=dict(l=10, r=10, t=50, b=10),
                      hovermode="x unified", legend=dict(orientation="h", y=1.12, x=0),
                      yaxis_title=ytitle, template="plotly_white")
    return fig


def power_chart(df, title="Power", show_flags=True, height=380, value_col="power", expected_col="expected_power", ytitle="Power (W)"):
    fig = go.Figure()
    if df is None or df.empty:
        return _layout(fig, title, height, ytitle)
    if expected_col in df:
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df[expected_col], name="Expected (model)",
                                 line=dict(color="#98A2B3", dash="dot", width=1.5)))
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df[value_col], name="Measured", mode="lines",
                             line=dict(color=PRIMARY, width=2.2), fill="tozeroy", fillcolor="rgba(31,95,191,0.08)"))
    if show_flags and "flagged" in df:
        f = df[df["flagged"]]
        if len(f):
            fig.add_trace(go.Scatter(x=f["timestamp"], y=f[value_col], mode="markers", name="Flagged reading",
                                     marker=dict(color="#C62828", size=9, symbol="x")))
    return _layout(fig, title, height, ytitle)


def forecast_chart(hist, fc, height=420, value_col="power", ytitle="Power (W)"):
    fig = go.Figure()
    if len(fc):
        fig.add_trace(go.Scatter(x=fc["target_time"], y=fc["yhat_upper"], line=dict(width=0),
                                 showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=fc["target_time"], y=fc["yhat_lower"], line=dict(width=0), fill="tonexty",
                                 fillcolor="rgba(242,140,40,0.25)", name="Prediction interval", hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=fc["target_time"], y=fc["yhat"], name="Forecast",
                                 line=dict(color=ACCENT, width=2.5, dash="dash")))
    if hist is not None and len(hist):
        fig.add_trace(go.Scatter(x=hist["timestamp"], y=hist[value_col], name="Actual",
                                 line=dict(color=PRIMARY, width=2.2)))
        fig.add_vline(x=hist["timestamp"].iloc[-1], line_dash="dot", line_color="#667085")
    return _layout(fig, "Actual usage and forecast", height, ytitle)


def bar_chart(df, x, y, title, color=None, height=320, ytitle=""):
    fig = go.Figure(go.Bar(x=df[x], y=df[y], marker_color=color or PRIMARY))
    fig.update_layout(title=dict(text=title, x=0.01), height=height, margin=dict(l=10, r=10, t=50, b=10),
                      yaxis_title=ytitle, template="plotly_white")
    return fig


def empty_state(msg):
    st.info(msg)
