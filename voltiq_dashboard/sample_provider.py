"""SampleDataProvider: serves the dashboard from your real daily-kWh dataset (SGCC format).

Reads data/sample_readings.csv and data/sample_devices.csv (made by prepare_sample_data.py).
The data ends on 31 Oct 2016, so that date is treated as "now" (data replay).
Forecast, anomaly score and theft probability come from model_hooks.py if you plugged your models in,
otherwise from simple statistical fallbacks (clearly labelled in Model Info).
"""
import math
import threading
from pathlib import Path

import numpy as np
import pandas as pd

import model_hooks
from config import DEFAULT_THRESHOLDS
from data_provider import (BaseDataProvider, DEVICE_COLUMNS, ALERT_COLUMNS, EVENT_COLUMNS, RELAY_COLUMNS,
                           FLEET_COLUMNS, MODEL_COLUMNS, FORECAST_COLUMNS, _severity)

OUTLIER = 500            # kWh/day above this is treated as a data error


class SampleDataProvider(BaseDataProvider):
    def __init__(self, data_dir=None):
        base = Path(__file__).parent
        d = Path(data_dir) if data_dir else base / "data"
        self._models_dir = base / "models"
        dev = pd.read_csv(d / "sample_devices.csv", parse_dates=["registered_on"])
        rd = pd.read_csv(d / "sample_readings.csv", parse_dates=["date"])
        self._lock = threading.RLock()
        self._thr = dict(DEFAULT_THRESHOLDS)
        self._devices = {r.device_id: dict(device_id=r.device_id, location=r.location, owner=r.owner, active=True,
                                           registered_on=r.registered_on, cons_no=r.cons_no, dataset_flag=r.dataset_flag)
                         for r in dev.itertuples()}
        self._start, self._end = rd["date"].min(), rd["date"].max()
        self._series = {}
        for did, g in rd.groupby("device_id"):
            s = g.set_index("date")["kwh"].astype(float).sort_index()
            self._series[did] = s.where(s <= OUTLIER)
        self._hook_notes = []
        self._scored = {did: self._score(did, s) for did, s in self._series.items()}
        self._acks, self._restored, self._manual_log, self._retrain = {}, set(), [], []
        self._events, self._alerts = [], []
        self._rebuild()

    # ------------------------------------------------------------------ scoring
    def _weekday_factor(self, s, base):
        ratio = (s / base.where(base > 0.3)).replace([np.inf, -np.inf], np.nan)
        f = ratio.groupby(ratio.index.dayofweek).median().reindex(range(7)).fillna(1.0)
        return (f / f.mean()).clip(0.7, 1.3)

    def _score(self, did, s):
        base = s.shift(1).rolling(28, min_periods=14).median()
        fac = self._weekday_factor(s, base)
        expected = base * s.index.dayofweek.map(fac).to_numpy()
        mad = (s.shift(1) - base).abs().rolling(56, min_periods=20).median() * 1.4826
        floor = (0.08 * base.clip(lower=0.5)).fillna(0.5)
        z = ((s - expected).abs() / (mad.clip(lower=floor) + 1e-6))
        anomaly = (1 - np.exp(-(z / 4) ** 2)).fillna(0.0)
        m7 = s.rolling(7, min_periods=4).mean()
        b56 = s.shift(7).rolling(90, min_periods=45).median()
        drop = (1 - m7 / b56.where(b56 > 0.5)).fillna(0.0)
        prob = 1 / (1 + np.exp(-(drop - 0.45) / 0.10))
        prob = prob.where(drop > 0, 0.0)
        # --- optional: your own trained models ----------------------------------------------
        for name, fn, target in (("anomaly_score", model_hooks.anomaly_score, "a"), ("theft_probability", model_hooks.theft_probability, "p")):
            try:
                out = fn(did, s)
                if out is not None:
                    out = pd.Series(out).reindex(s.index).fillna(0.0).clip(0, 1)
                    anomaly, prob = (out, prob) if target == "a" else (anomaly, out)
                    self._hook_notes.append(name)
            except Exception as e:                                   # never break the dashboard
                self._hook_notes.append(f"{name} hook failed: {e}")
        df = pd.DataFrame({"kwh": s, "expected_kwh": expected, "anomaly_score": anomaly.round(3),
                           "theft_prob": prob.round(3)})
        df["energy"] = s.fillna(0).cumsum().round(2)
        return df

    # ------------------------------------------------------------------ events (derived from scores)
    def _rebuild(self):
        thr, tau, n = self._thr["anomaly_threshold"], self._thr["theft_prob_tau"], int(self._thr["n_windows"])
        old = {(a["device_id"], a["created_at"]): (a["acknowledged_by"], a["acknowledged_at"]) for a in self._alerts}
        old.update(self._acks)
        events, alerts = [], []
        cutoff = self._end - pd.Timedelta(days=365)
        for did, df in self._scored.items():
            theft_run, last_theft, last_anom, anom_run = 0, None, None, 0
            for ts, r in df.iterrows():
                theft_run = theft_run + 1 if r.theft_prob >= tau else 0
                anom_run = anom_run + 1 if (r.anomaly_score >= thr and r.theft_prob < tau) else 0
                if theft_run == n and (last_theft is None or (ts - last_theft).days > 30):
                    last_theft = ts
                    if ts < cutoff:
                        continue
                    recent = (self._end - ts).days <= 30
                    events.append(self._ev(did, ts, "Theft", r.theft_prob, r.anomaly_score, "Confirmed" if recent else "Historical", n))
                elif anom_run == 2 and ts >= cutoff and (last_anom is None or (ts - last_anom).days > 21):
                    last_anom = ts
                    events.append(self._ev(did, ts, "Anomaly", r.theft_prob, r.anomaly_score, "Warning", 2))
        for e in events:
            if (e["device_id"], e["detected_at"]) in self._restored and e["status"] == "Confirmed":
                e["status"] = "Restored"
            msg = ("Theft suspected: sustained drop in consumption for %d consecutive days." % e["windows_confirmed"]
                   if e["class_label"] == "Theft" else "Unusual consumption compared with the recent pattern.")
            a = dict(alert_id="AL-" + e["event_id"][3:], created_at=e["detected_at"], device_id=e["device_id"],
                     severity=_severity(e["probability"]) if e["class_label"] == "Theft" else ("medium" if e["anomaly_score"] >= 0.85 else "low"),
                     event_type=e["class_label"], anomaly_score=e["anomaly_score"], theft_probability=e["probability"],
                     status="Open", acknowledged_by=None, acknowledged_at=None, message=msg, event_id=e["event_id"])
            by, at = old.get((e["device_id"], e["detected_at"]), (None, None))
            a.update(acknowledged_by=by, acknowledged_at=at)
            alerts.append(a)
        self._events, self._alerts = events, alerts

    def _ev(self, did, ts, cls, prob, score, status, windows):
        return dict(event_id=f"EV-{did[-2:]}-{ts:%Y%m%d}-{cls[0]}", device_id=did, detected_at=ts, class_label=cls,
                    probability=float(round(prob, 2)), windows_confirmed=windows, status=status,
                    model_id="user_model" if "theft_probability" in self._hook_notes else "fallback_sustained_drop",
                    anomaly_score=float(round(score, 2)))

    def _open_since(self, did):
        c = [e["detected_at"] for e in self._events if e["device_id"] == did and e["status"] == "Confirmed"]
        return max(c) if c else None

    # ------------------------------------------------------------------ capabilities & devices
    def get_capabilities(self):
        return dict(granularity="daily", now=self._end, data_start=self._start, data_end=self._end,
                    value_col="kwh", expected_col="expected_kwh", unit="kWh", unit_label="kWh per day",
                    has_electrical=False, can_simulate=False,
                    source=f"SGCC sample data (daily kWh) - replay up to {self._end:%d %b %Y}")

    def get_devices(self, owner=None):
        df = pd.DataFrame([{c: d[c] for c in DEVICE_COLUMNS} for d in self._devices.values()], columns=DEVICE_COLUMNS)
        return (df[df["owner"] == owner] if owner else df).reset_index(drop=True)

    def register_device(self, device_id, location, owner):
        return False, "Adding devices needs real data for them. Add the consumer with prepare_sample_data.py --pick."

    def update_device(self, device_id, location, owner, active):
        if device_id not in self._devices:
            return False, "Unknown device."
        self._devices[device_id].update(location=location.strip(), owner=owner, active=bool(active))
        return True, f"Device '{device_id}' updated."

    # ------------------------------------------------------------------ readings
    def _frame(self, did):
        df = self._scored[did].copy()
        df["power"] = (df["kwh"] * 1000 / 24).round(0)                 # daily mean power in W
        df["expected_power"] = (df["expected_kwh"] * 1000 / 24).round(0)
        df["voltage"] = np.nan
        df["current"] = np.nan
        os_ = self._open_since(did)
        df["relay_state"] = np.where((df.index >= os_) if os_ is not None else False, "OPEN", "CLOSED")
        df["flagged"] = df["anomaly_score"] >= self._thr["anomaly_threshold"]
        df.index.name = "timestamp"
        return df.reset_index()

    def get_readings(self, device_id, start, end, freq="1D"):
        df = self._frame(device_id)
        end = min(pd.Timestamp(end), self._end)
        return df[(df["timestamp"] >= pd.Timestamp(start).normalize()) & (df["timestamp"] <= end)].reset_index(drop=True)

    def get_latest_reading(self, device_id):
        df = self._frame(device_id)
        valid = df[df["kwh"].notna()]
        r = (valid.iloc[-1] if len(valid) else df.iloc[-1]).to_dict()
        r.update(device_id=device_id, connected=(self._end - r["timestamp"]).days <= 3,
                 sync_status="daily batch (replayed dataset)")
        return r

    def get_device_status(self, device_id):
        if not self.get_latest_reading(device_id)["connected"]:
            return "Offline"
        if self._open_since(device_id) is not None:
            return "Theft detected"
        recent = self._frame(device_id).tail(3)
        risky = recent["flagged"].any() or recent["theft_prob"].max() >= self._thr["theft_prob_tau"]
        return "Warning" if risky else "Normal"

    def get_fleet_overview(self):
        rows = []
        for did, d in self._devices.items():
            r = self.get_latest_reading(did)
            df = self._frame(did).tail(7)
            rows.append(dict(device_id=did, location=d["location"], owner=d["owner"], status=self.get_device_status(did),
                             last_reading=r["timestamp"], voltage=r["voltage"], power_w=r["power"],
                             relay_state="OPEN" if self._open_since(did) is not None else "CLOSED",
                             theft_risk=round(float(df["theft_prob"].max()), 2),
                             open_alerts=sum(1 for a in self._alerts if a["device_id"] == did and a["acknowledged_by"] is None),
                             dataset_label=d["dataset_flag"]))
        return pd.DataFrame(rows, columns=FLEET_COLUMNS + ["dataset_label"])

    # ------------------------------------------------------------------ forecast
    def get_forecast(self, device_id, horizon_hours=24, step_minutes=1440):
        n = max(1, int(round(horizon_hours / 24)))
        s = self._series[device_id]
        idx = pd.date_range(self._end + pd.Timedelta(days=1), periods=n, freq="D")
        try:
            out = model_hooks.forecast(device_id, s, n)
            if out is not None:
                out = out.copy(); out["model_id"] = "user_model"
                return out[FORECAST_COLUMNS]
        except Exception as e:
            self._hook_notes.append(f"forecast hook failed: {e}")
        base = s.tail(28).median()
        fac = self._weekday_factor(s, s.shift(1).rolling(28, min_periods=14).median())
        yhat = np.array([base * fac[d.dayofweek] for d in idx]).clip(min=0)
        sd = self._resid_std(device_id)
        width = 1.28 * sd * np.sqrt(1 + 0.05 * np.arange(n))
        return pd.DataFrame({"target_time": idx, "yhat": yhat.round(2), "yhat_lower": (yhat - width).clip(min=0).round(2),
                             "yhat_upper": (yhat + width).round(2), "model_id": "fallback_weekday_median"})

    def _resid_std(self, did):
        df = self._scored[did].tail(60)
        r = (df["kwh"] - df["expected_kwh"]).dropna()
        return float(r.std()) if len(r) > 5 else 1.0

    def get_forecast_metrics(self, device_id):
        df = self._scored[device_id].tail(30)
        act = df["kwh"]
        base = self._series[device_id].shift(7).reindex(df.index)
        ok = act.notna() & df["expected_kwh"].notna() & base.notna()
        mae = float((act[ok] - df["expected_kwh"][ok]).abs().mean()) if ok.any() else float("nan")
        rmse = float(np.sqrt(((act[ok] - df["expected_kwh"][ok]) ** 2).mean())) if ok.any() else float("nan")
        mae_b = float((act[ok] - base[ok]).abs().mean()) if ok.any() else float("nan")
        imp = 100 * (1 - mae / mae_b) if ok.any() and mae_b else float("nan")
        user = "forecast" in " ".join(self._hook_notes)
        return dict(model="Your model" if user else "Weekday median (fallback)", version="-", unit="kWh",
                    mae=round(mae, 2), rmse=round(rmse, 2), baseline_mae=round(mae_b, 2),
                    improvement_pct=round(imp, 1) if imp == imp else 0.0,
                    backtest="last 30 days, one-day-ahead vs 'same weekday last week'")

    # ------------------------------------------------------------------ alerts / events / relay
    def get_alerts(self, device_ids, start, end):
        rows = [a for a in self._alerts if a["device_id"] in device_ids and pd.Timestamp(start) <= a["created_at"] <= pd.Timestamp(end)]
        df = pd.DataFrame(rows, columns=ALERT_COLUMNS)
        if len(df):
            df["status"] = np.where(df["acknowledged_by"].notna(), "Acknowledged", "Open")
            df = df.sort_values("created_at", ascending=False)
        return df.reset_index(drop=True)

    def acknowledge_alert(self, alert_id, user):
        with self._lock:
            for a in self._alerts:
                if a["alert_id"] == alert_id:
                    if a["acknowledged_by"]:
                        return False, "Already acknowledged."
                    a.update(acknowledged_by=user, acknowledged_at=pd.Timestamp.now().floor("s"))
                    self._acks[(a["device_id"], a["created_at"])] = (a["acknowledged_by"], a["acknowledged_at"])
                    return True, f"Alert {alert_id} acknowledged."
        return False, "Alert not found."

    def get_theft_events(self, device_ids, start, end):
        rows = [e for e in self._events if e["device_id"] in device_ids and pd.Timestamp(start) <= e["detected_at"] <= pd.Timestamp(end)]
        df = pd.DataFrame(rows, columns=EVENT_COLUMNS)
        return df.sort_values("detected_at", ascending=False).reset_index(drop=True) if len(df) else df

    def get_relay_state(self, device_id):
        s = self._open_since(device_id)
        return dict(state="OPEN", since=s, reason="Confirmed theft (replayed data)") if s is not None else dict(state="CLOSED", since=None, reason="")

    def get_relay_log(self, device_ids, start, end):
        rows = [dict(time=e["detected_at"], device_id=e["device_id"], action="OPEN", user="system",
                     reason=f"Confirmed theft (p={e['probability']:.2f}, {e['windows_confirmed']} days) - simulated cut-off")
                for e in self._events if e["class_label"] == "Theft" and e["status"] in ("Confirmed", "Restored")]
        rows += self._manual_log
        df = pd.DataFrame([r for r in rows if r["device_id"] in device_ids and pd.Timestamp(start) <= r["time"] <= pd.Timestamp(end)],
                          columns=RELAY_COLUMNS)
        return df.sort_values("time", ascending=False).reset_index(drop=True) if len(df) else df

    def restore_load(self, device_id, user, reason):
        with self._lock:
            s = self._open_since(device_id)
            if s is None:
                return False, "The relay is already closed."
            self._restored.add((device_id, s))
            self._manual_log.append(dict(time=pd.Timestamp.now().floor("s"), device_id=device_id, action="CLOSE",
                                         reason=reason or "Restored after review", user=user))
            self._rebuild()
        return True, f"Restore command issued for {device_id}."

    def simulate_theft(self, device_id, user):
        return False, "Not available with real sample data."

    # ------------------------------------------------------------------ models & settings
    def get_model_info(self):
        f = self._models_dir / "model_info.csv"
        if f.exists():
            return pd.read_csv(f, parse_dates=["trained_at"]).reindex(columns=MODEL_COLUMNS)
        used = ", ".join(self._hook_notes) or "none"
        t = pd.Timestamp.now().normalize()
        rows = [("fallback_forecast", "Usage forecasting", "Weekday median", "fallback", t, None, None, None, None, None,
                 "Built-in method. Plug in your model via model_hooks.py"),
                ("fallback_anomaly", "Anomaly scoring", "Robust z-score", "fallback", t, None, None, None, None, None,
                 "Built-in method. Plug in your model via model_hooks.py"),
                ("fallback_theft", "Theft classification", "Sustained-drop rule", "fallback", t, None, None, None, None, None,
                 f"Heuristic, not a trained classifier. Hooks active: {used}")]
        return pd.DataFrame(rows, columns=MODEL_COLUMNS)

    def request_retrain(self, user):
        return "Placeholder: run your training notebook, save the model into models/ and plug it in via model_hooks.py."

    def get_thresholds(self):
        return dict(self._thr)

    def set_thresholds(self, values):
        with self._lock:
            self._thr.update(values)
            self._rebuild()
