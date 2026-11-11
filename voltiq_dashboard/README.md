# VoltIQ Dashboard (Streamlit)

Dashboard for the VoltIQ real-time electricity forecasting and theft-detection project, built from the SRS.
It runs today on **mock data**. Real data can be plugged in later without touching the UI.

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Using your own dataset (SGCC daily-kWh format)
The app has two data modes (set in `config.py` or with the environment variable `VOLTIQ_DATA_MODE`):
* `sample` (default) - reads `data/sample_readings.csv` + `data/sample_devices.csv`, made from your dataset.
* `mock` - the old synthetic minute-level demo data.

**What changes with daily data:** the dataset has one kWh value per consumer per day, with no voltage, current or
minute-level power. So in sample mode the Live page becomes "Latest Consumption" (kWh/day, no V/I, no 5-second
refresh), the forecast horizon is in days, and the data ends on 31 Oct 2016, which the app treats as "now" (replay).
Power in the tables is the daily mean (kWh x 1000 / 24).

**Choosing other consumers:**
```bash
python prepare_sample_data.py path/to/data_set.csv                 # picks 4 theft + 4 normal automatically
python prepare_sample_data.py path/to/data_set.csv --per-class 3
python prepare_sample_data.py path/to/data_set.csv --pick CONS_NO_1 CONS_NO_2 ...   # your own choice
```
The automatic pick only makes a clear demo (theft-labelled consumers whose usage fell 50-90 %, normal ones with stable
usage). It is not a test of any model. The big CSV is only needed for this step, not to run the dashboard.

**Plugging in your trained models:** edit `model_hooks.py` (3 optional functions: forecast, theft_probability,
anomaly_score) and put the model files in `models/`. The features must be built exactly as in your training code.
Until then the dashboard uses built-in fallbacks: weekday-median forecast, robust z-score anomaly score and a
"sustained drop" rule for theft probability. These are simple heuristics, not trained models, and Model Info says so.

**Replay behaviour:** alerts and theft events are computed from the data. A theft confirmed in the last 30 days of the
data opens the relay (simulated); older events are shown as Historical. Relay actions are not real hardware commands.

## Demo logins
| user | password | role |
|---|---|---|
| admin | admin123 | administrator (all devices, restore load, thresholds, models) |
| consumer1 | consumer123 | owns meter_01 and meter_03 |
| consumer2 | consumer123 | owns meter_02, meter_04, meter_05 |

Quick demo: log in as `consumer1` and open meter_03 (theft already confirmed, relay OPEN) -> acknowledge the
alert -> log in as `admin`, Relay Control -> restore the load. Admin can also simulate a new theft event
(Relay Control -> demo tool). meter_05 is shown offline on purpose.

## Folder structure
```
app.py            entry point: login, sidebar (device, date range, view), routing
config.py         constants, default thresholds, colours, page lists
auth.py           login, roles, salted PBKDF2 password hashes (demo users)
context.py        Ctx object passed to every view
data_provider.py  BaseDataProvider contract + MockDataProvider + RealDataProvider stub
sample_provider.py serves your real daily dataset (data/ folder)
model_hooks.py    plug in your trained models (forecast / theft / anomaly)
prepare_sample_data.py  picks consumers from the big CSV -> data/
data/, models/    sample files, and the folder for your model files
ui.py             CSS, metric cards, badges, colour-coded tables, Plotly charts
views/            live, forecast, alerts, relay, reports, model_info, fleet (admin), admin (admin)
```

## SRS coverage
FR-22 live view - FR-23 forecast + interval - FR-24 anomalies/alerts (colour-coded) - FR-25 device and date filters -
FR-26 CSV/Excel reports - FR-27 login + roles - FR-28 device registration and thresholds - FR-29 alert acknowledgement -
FR-17 model info + retrain placeholder - FR-18..21 relay status, admin-only restore with confirmation, action log.

## Replacing the mock data with real data
1. In `data_provider.py` implement every method of `RealDataProvider` (same names as `BaseDataProvider`).
2. In `app.py` change `MockDataProvider()` to `RealDataProvider(...)`.

Columns each method must return:

| method | returns |
|---|---|
| get_capabilities() | dict: granularity ('minute'/'daily'), now, data_start, data_end, value_col, expected_col, unit, unit_label, has_electrical, can_simulate, source |
| get_devices(owner) | device_id, location, owner, registered_on, active |
| get_latest_reading(id) | dict: timestamp, voltage, current, power, energy, relay_state, anomaly_score, flagged, connected, sync_status |
| get_readings(id, start, end, freq) | timestamp, voltage, current, power, energy, relay_state, anomaly_score, flagged (optional: expected_power) |
| get_device_status(id) | 'Normal' / 'Warning' / 'Theft detected' / 'Offline' |
| get_fleet_overview() | device_id, location, owner, status, last_reading, voltage, power_w, relay_state, theft_risk, open_alerts |
| get_forecast(id, hours, step) | target_time, yhat, yhat_lower, yhat_upper, model_id |
| get_forecast_metrics(id) | dict: model, version, mae, rmse, baseline_mae, improvement_pct, backtest |
| get_alerts(ids, start, end) | alert_id, created_at, device_id, severity, event_type, anomaly_score, theft_probability, status, acknowledged_by, acknowledged_at, message, event_id |
| acknowledge_alert(id, user) | (ok, message) |
| get_theft_events(ids, start, end) | event_id, device_id, detected_at, class_label, probability, windows_confirmed, status, model_id |
| get_relay_state(id) | dict: state ('OPEN'/'CLOSED'), since, reason |
| get_relay_log(ids, start, end) | time, device_id, action ('OPEN'/'CLOSE'), reason, user |
| restore_load(id, user, reason) | (ok, message) - queue a CLOSE command for the device |
| get_model_info() | model_id, purpose, algorithm, version, trained_at, mae, rmse, precision, recall, f1, notes |
| get_thresholds() / set_thresholds(d) | dict: anomaly_threshold, theft_prob_tau, n_windows |
| register_device / update_device | (ok, message) |
| request_retrain(user) | status message |
| simulate_theft(id, user) | demo only; leave unimplemented or hide the button |

Also replace the demo users in `auth.py` with a database table (keep storing only salted hashes).
