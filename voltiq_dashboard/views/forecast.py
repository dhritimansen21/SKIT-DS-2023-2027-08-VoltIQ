"""Usage forecast with prediction interval (FR-23) and error metrics."""
import pandas as pd
import streamlit as st

import ui


def render(ctx):
    p, dev = ctx.provider, ctx.device_id
    caps = p.get_capabilities()
    daily = caps["granularity"] == "daily"
    ui.page_header("Usage Forecast", f"Device {dev} - short-term prediction with prediction interval")
    now = caps["now"] if daily else pd.Timestamp.now()
    if daily:
        days = st.select_slider("Forecast horizon", options=[7, 14, 30], value=14, format_func=lambda d: f"{d} days")
        hist = p.get_readings(dev, now - pd.Timedelta(days=60), now)
        fc = p.get_forecast(dev, days * 24, 1440)
        col, unit = "kwh", "kWh"
    else:
        h = st.select_slider("Forecast horizon", options=[6, 12, 24, 48], value=24, format_func=lambda x: f"{x} h")
        hist = p.get_readings(dev, now - pd.Timedelta(hours=24), now, "30min")
        fc = p.get_forecast(dev, h, 30)
        col, unit = "power", "W"
    m = p.get_forecast_metrics(dev)
    unit = m.get("unit", unit)

    c = st.columns(5)
    with c[0]:
        ui.metric_card("Model", m["model"], "", m["version"])
    with c[1]:
        ui.metric_card("MAE", f"{m['mae']:.2f}" if daily else f"{m['mae']:.1f}", unit, "mean absolute error")
    with c[2]:
        ui.metric_card("RMSE", f"{m['rmse']:.2f}" if daily else f"{m['rmse']:.1f}", unit, "root mean squared error")
    with c[3]:
        ui.metric_card("Baseline MAE", f"{m['baseline_mae']:.2f}" if daily else f"{m['baseline_mae']:.1f}", unit,
                       "same weekday last week" if daily else "same hour, previous day")
    with c[4]:
        ui.metric_card("Improvement", f"{m['improvement_pct']:.0f}", "%", "lower error than baseline")
    st.caption(f"Metrics from a backtest: {m['backtest']}.")

    if fc.empty:
        return ui.empty_state("No forecast available for this device yet.")
    st.plotly_chart(ui.forecast_chart(hist, fc, value_col=col, ytitle=caps["unit_label"]), width="stretch")
    c1, c2, c3 = st.columns(3)
    if daily:
        c1.metric("Expected energy in horizon", f"{fc['yhat'].sum():.1f} kWh")
        c2.metric("Highest expected day", f"{fc['yhat'].max():.2f} kWh", f"{fc.loc[fc['yhat'].idxmax(), 'target_time']:%a %d %b}")
        c3.metric("Lowest expected day", f"{fc['yhat'].min():.2f} kWh")
    else:
        c1.metric("Expected energy in horizon", f"{fc['yhat'].sum() * 0.5 / 1000:.1f} kWh")
        c2.metric("Expected peak", f"{fc['yhat'].max():.0f} W", f"at {fc.loc[fc['yhat'].idxmax(), 'target_time']:%H:%M}")
        c3.metric("Expected minimum", f"{fc['yhat'].min():.0f} W")
    with st.expander("Forecast table"):
        st.dataframe(fc, width="stretch", hide_index=True)
        st.download_button("Download forecast (CSV)", fc.to_csv(index=False).encode(), f"forecast_{dev}.csv", "text/csv")
