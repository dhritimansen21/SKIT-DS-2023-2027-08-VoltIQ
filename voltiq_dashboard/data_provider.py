"""Data layer for the VoltIQ dashboard.

The UI talks ONLY to the functions of BaseDataProvider.
  * MockDataProvider  - generates realistic demo data (used now, no database needed).
  * RealDataProvider  - stub: implement the same functions against your database/API later.
Switch providers in app.get_provider(). The UI code does not need to change.
"""
import threading
import numpy as np
import pandas as pd

from config import DEFAULT_THRESHOLDS, WINDOW_MINUTES

READING_COLUMNS = ["timestamp", "voltage", "current", "power", "energy", "relay_state",
                   "anomaly_score", "flagged"]          # optional extra column: expected_power
ALERT_COLUMNS = ["alert_id", "created_at", "device_id", "severity", "event_type", "anomaly_score",
                 "theft_probability", "status", "acknowledged_by", "acknowledged_at", "message", "event_id"]
EVENT_COLUMNS = ["event_id", "device_id", "detected_at", "class_label", "probability",
                 "windows_confirmed", "status", "model_id"]
RELAY_COLUMNS = ["time", "device_id", "action", "reason", "user"]
DEVICE_COLUMNS = ["device_id", "location", "owner", "registered_on", "active"]
FORECAST_COLUMNS = ["target_time", "yhat", "yhat_lower", "yhat_upper", "model_id"]
FLEET_COLUMNS = ["device_id", "location", "owner", "status", "last_reading", "voltage", "power_w",
                 "relay_state", "theft_risk", "open_alerts"]
MODEL_COLUMNS = ["model_id", "purpose", "algorithm", "version", "trained_at", "mae", "rmse",
                 "precision", "recall", "f1", "notes"]


class BaseDataProvider:
    """Contract the dashboard relies on. Each method says what it must return."""

    # ---- capabilities ------------------------------------------------------------
    def get_capabilities(self) -> dict:
        """Tells the views what the data looks like. Default = minute-level electrical data (mock)."""
        return dict(granularity="minute", now=None, data_start=None, data_end=None, value_col="power",
                    expected_col="expected_power", unit="W", unit_label="Power (W)", has_electrical=True,
                    can_simulate=True, source="Mock data (synthetic)")

    # ---- devices -----------------------------------------------------------------
    def get_devices(self, owner=None) -> pd.DataFrame:
        """DataFrame[DEVICE_COLUMNS]; if owner is given, only that user's devices."""
        raise NotImplementedError

    def register_device(self, device_id, location, owner):
        """Create a device. Return (ok: bool, message: str)."""
        raise NotImplementedError

    def update_device(self, device_id, location, owner, active):
        """Edit a device. Return (ok: bool, message: str)."""
        raise NotImplementedError

    # ---- readings ----------------------------------------------------------------
    def get_latest_reading(self, device_id) -> dict:
        """dict with timestamp, voltage, current, power, energy, relay_state, anomaly_score, flagged,
        connected (bool), sync_status (str)."""
        raise NotImplementedError

    def get_readings(self, device_id, start, end, freq="5min") -> pd.DataFrame:
        """DataFrame[READING_COLUMNS] (+ optional expected_power) between start and end, resampled to freq."""
        raise NotImplementedError

    def get_device_status(self, device_id) -> str:
        """One of: 'Normal', 'Warning', 'Theft detected', 'Offline'."""
        raise NotImplementedError

    def get_fleet_overview(self) -> pd.DataFrame:
        """DataFrame[FLEET_COLUMNS], one row per device (admin Fleet Overview)."""
        raise NotImplementedError

    # ---- forecasting -------------------------------------------------------------
    def get_forecast(self, device_id, horizon_hours=24, step_minutes=30) -> pd.DataFrame:
        """DataFrame[FORECAST_COLUMNS] for the next horizon_hours."""
        raise NotImplementedError

    def get_forecast_metrics(self, device_id) -> dict:
        """dict(model, version, mae, rmse, baseline_mae, improvement_pct, backtest) in watts."""
        raise NotImplementedError

    # ---- alerts / events ---------------------------------------------------------
    def get_alerts(self, device_ids, start, end) -> pd.DataFrame:
        """DataFrame[ALERT_COLUMNS] created between start and end for the given devices."""
        raise NotImplementedError

    def acknowledge_alert(self, alert_id, user):
        """Store who acknowledged the alert and when. Return (ok, message)."""
        raise NotImplementedError

    def get_theft_events(self, device_ids, start, end) -> pd.DataFrame:
        """DataFrame[EVENT_COLUMNS]."""
        raise NotImplementedError

    # ---- relay -------------------------------------------------------------------
    def get_relay_state(self, device_id) -> dict:
        """dict(state='OPEN'|'CLOSED', since=Timestamp|None, reason=str)."""
        raise NotImplementedError

    def get_relay_log(self, device_ids, start, end) -> pd.DataFrame:
        """DataFrame[RELAY_COLUMNS] of every cut-off / restore action."""
        raise NotImplementedError

    def restore_load(self, device_id, user, reason):
        """Queue a restore (close) command and log it. Return (ok, message)."""
        raise NotImplementedError

    def simulate_theft(self, device_id, user):
        """DEMO ONLY (mock): create a theft event and cut the load. Real provider may raise."""
        raise NotImplementedError

    # ---- models & settings -------------------------------------------------------
    def get_model_info(self) -> pd.DataFrame:
        """DataFrame[MODEL_COLUMNS]."""
        raise NotImplementedError

    def request_retrain(self, user) -> str:
        """Trigger (or queue) model retraining. Return a status message."""
        raise NotImplementedError

    def get_thresholds(self) -> dict:
        """dict(anomaly_threshold, theft_prob_tau, n_windows)."""
        raise NotImplementedError

    def set_thresholds(self, values: dict):
        raise NotImplementedError


class RealDataProvider(BaseDataProvider):
    """TODO: implement every method of BaseDataProvider against your database / backend.
    Example: self.conn = sqlite3.connect('voltiq.db'); get_readings() -> pd.read_sql(...).
    See README.md for the exact columns each method must return."""

    def __init__(self, db_path="voltiq.db"):
        self.db_path = db_path


# ============================================================================================
#                                      MOCK PROVIDER
# ============================================================================================
EPOCH = pd.Timestamp("1970-01-01")
ORIGIN = pd.Timestamp("2026-01-01")
HOURLY = np.array([0.35, 0.30, 0.28, 0.27, 0.30, 0.45, 0.75, 1.00, 0.85, 0.65, 0.60, 0.62,
                   0.70, 0.68, 0.60, 0.62, 0.75, 0.95, 1.25, 1.35, 1.20, 0.95, 0.65, 0.45])


def _noise(seed, t, k=0):
    """Deterministic pseudo-random numbers in [0, 1) from timestamps (so charts are repeatable)."""
    x = np.sin(t * 12.9898 + seed * 78.233 + k * 37.719) * 43758.5453
    return x - np.floor(x)


def _severity(prob):
    return "critical" if prob >= 0.90 else "high" if prob >= 0.75 else "medium" if prob >= 0.50 else "low"


class MockDataProvider(BaseDataProvider):
    def __init__(self):
        self._lock = threading.RLock()
        now = pd.Timestamp.now().floor("min")
        h, m = pd.Timedelta(hours=1), pd.Timedelta(minutes=1)
        self._thresholds = dict(DEFAULT_THRESHOLDS)
        specs = [("meter_01", "House A - Ground floor", "consumer1", 1800),
                 ("meter_02", "Hostel Block B", "consumer2", 2400),
                 ("meter_03", "Shop 12 - Main Market", "consumer1", 1500),
                 ("meter_04", "Library Annex", "consumer2", 3200),
                 ("meter_05", "Workshop", "consumer2", 900)]
        self._devices = {}
        for i, (did, loc, owner, peak) in enumerate(specs, start=1):
            self._devices[did] = dict(device_id=did, location=loc, owner=owner, active=True,
                                      registered_on=(now - pd.Timedelta(days=60 - i)).normalize(),
                                      seed=i, peak_w=peak, offset_kwh=900 + 310 * i)
        self._offline_since = {"meter_05": now - 3 * h}                       # demo: one unit is offline
        self._theft_windows = {"meter_03": [(now - 3 * h - 15 * m, now - 3 * h)]}
        self._warn_windows = {"meter_02": [(now - 26 * h - 10 * m, now - 26 * h)],
                              "meter_05": [(now - 49 * h - 10 * m, now - 49 * h)],
                              "meter_01": [(now - 30 * h, now - 30 * h + 10 * m)]}
        self._relay_intervals = {"meter_03": [[now - 3 * h, None]]}           # relay opened after theft
        self._events, self._alerts, self._relay_log = [], [], []
        self._retrain_requests = []
        self._seq = 0
        # --- seed history -------------------------------------------------------------
        e = self._add_event("meter_03", now - 3 * h, "Theft", 0.93, 0.96, "Confirmed", 3)
        self._add_alert(e, "Theft confirmed (p=0.93 over 3 consecutive windows). Load cut off.")
        self._relay_log.append(dict(time=now - 3 * h, device_id="meter_03", action="OPEN",
                                    reason="Confirmed theft (p=0.93, 3 windows)", user="system"))
        e = self._add_event("meter_02", now - 26 * h, "Anomaly", 0.52, 0.67, "Warning", 1)
        a = self._add_alert(e, "Unusual drop in recorded power. Monitoring continued.")
        a.update(acknowledged_by="admin", acknowledged_at=now - 25 * h)
        e = self._add_event("meter_05", now - 49 * h - 10 * m, "Anomaly", 0.31, 0.64, "Warning", 1)
        a = self._add_alert(e, "Short anomaly, low probability of theft.")
        a.update(acknowledged_by="consumer2", acknowledged_at=now - 48 * h)
        e = self._add_event("meter_01", now - 30 * h + 10 * m, "Anomaly", 0.44, 0.66, "Warning", 1)
        self._add_alert(e, "Short dip in usage. Please check your connection.")

    # ---------------------------------------------------------------- helpers
    def _now(self):
        return pd.Timestamp.now()

    def _next(self, prefix):
        self._seq += 1
        return f"{prefix}-{self._seq:04d}"

    def _add_event(self, dev, when, cls, prob, score, status, windows):
        ev = dict(event_id=self._next("EV"), device_id=dev, detected_at=when, class_label=cls,
                  probability=prob, windows_confirmed=windows, status=status,
                  model_id="theft_clf_v1.2", anomaly_score=score)
        self._events.append(ev)
        return ev

    def _add_alert(self, ev, message):
        al = dict(alert_id=self._next("AL"), created_at=ev["detected_at"], device_id=ev["device_id"],
                  severity=_severity(ev["probability"]), event_type=ev["class_label"],
                  anomaly_score=ev["anomaly_score"], theft_probability=ev["probability"],
                  status="Open", acknowledged_by=None, acknowledged_at=None,
                  message=message, event_id=ev["event_id"])
        self._alerts.append(al)
        return al

    @staticmethod
    def _mask(idx, windows):
        m = np.zeros(len(idx), dtype=bool)
        for s, e in windows:
            m |= (idx >= s) & (idx < e)
        return m

    def _open_mask(self, dev, idx):
        m = np.zeros(len(idx), dtype=bool)
        for s, e in self._relay_intervals.get(dev, []):
            m |= (idx >= s) & (idx < (e if e is not None else pd.Timestamp.max))
        return m

    def _expected(self, dev, idx):
        d = self._devices[dev]
        hour = idx.hour + idx.minute / 60 + idx.second / 3600
        prof = np.interp(hour, np.arange(25), np.append(HOURLY, HOURLY[0]))
        wk = np.where(idx.dayofweek >= 5, 1.1, 1.0)
        return d["peak_w"] * prof * wk / 1.35

    def _generate(self, dev, idx):
        d = self._devices[dev]
        seed = d["seed"]
        t = np.asarray((idx - EPOCH).total_seconds(), dtype=float)
        n1, n2, n3 = _noise(seed, t, 1), _noise(seed, t, 2), _noise(seed, t, 3)
        exp = self._expected(dev, idx)
        power = exp * (1 + (n2 - 0.5) * 0.12)
        warn = self._mask(idx, self._warn_windows.get(dev, []))
        theft = self._mask(idx, self._theft_windows.get(dev, []))
        power = np.where(warn, exp * (0.55 + 0.1 * n3), power)
        power = np.where(theft, exp * np.where(n3 > 0.88, 1.15, 0.30 + 0.2 * n3), power)  # drops + odd spikes
        opened = self._open_mask(dev, idx)
        power = np.where(opened, 0.0, power)
        voltage = 230 + (n1 - 0.5) * 6
        current = power / (voltage * 0.95)
        dev_rel = np.abs(power - exp) / np.maximum(exp, 1)
        score = np.clip(1.6 * dev_rel + 0.03 * n1, 0, 1)
        score = np.where(opened, 0.0, score)                       # an open relay is intentional, not an anomaly
        k = d["peak_w"] * 0.52 / 3.6e6                              # kWh per second at mean load
        energy = d["offset_kwh"] + (idx - ORIGIN).total_seconds().to_numpy() * k
        thr = self._thresholds["anomaly_threshold"]
        return pd.DataFrame({
            "timestamp": idx, "voltage": voltage.round(1), "current": current.round(2),
            "power": power.round(0), "energy": np.round(energy, 3),
            "relay_state": np.where(opened, "OPEN", "CLOSED"), "anomaly_score": score.round(3),
            "flagged": score >= thr, "expected_power": exp.round(0)})

    # ---------------------------------------------------------------- devices
    def get_devices(self, owner=None):
        rows = [{c: d[c] for c in DEVICE_COLUMNS} for d in self._devices.values()]
        df = pd.DataFrame(rows, columns=DEVICE_COLUMNS)
        if owner:
            df = df[df["owner"] == owner]
        return df.reset_index(drop=True)

    def register_device(self, device_id, location, owner):
        device_id = (device_id or "").strip()
        if not device_id or not location.strip():
            return False, "Device ID and location are required."
        if device_id in self._devices:
            return False, f"Device '{device_id}' already exists."
        with self._lock:
            n = len(self._devices) + 1
            self._devices[device_id] = dict(device_id=device_id, location=location.strip(), owner=owner,
                                            active=True, registered_on=self._now().normalize(),
                                            seed=n, peak_w=1500, offset_kwh=1000)
        return True, f"Device '{device_id}' registered."

    def update_device(self, device_id, location, owner, active):
        if device_id not in self._devices:
            return False, "Unknown device."
        with self._lock:
            self._devices[device_id].update(location=location.strip(), owner=owner, active=bool(active))
        return True, f"Device '{device_id}' updated."

    # ---------------------------------------------------------------- readings
    def get_latest_reading(self, device_id):
        off = self._offline_since.get(device_id)
        ts = off if off is not None else self._now().floor("s")
        row = self._generate(device_id, pd.DatetimeIndex([ts])).iloc[0].to_dict()
        row.update(device_id=device_id, connected=off is None,
                   sync_status="synced" if off is None else "buffering on microSD (offline)")
        return row

    def get_readings(self, device_id, start, end, freq="5min"):
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        off = self._offline_since.get(device_id)
        if off is not None:
            end = min(end, off)
        end = min(end, self._now())
        if start >= end:
            return pd.DataFrame(columns=READING_COLUMNS + ["expected_power"])
        idx = pd.date_range(start.floor(freq), end, freq=freq)
        return self._generate(device_id, idx).reset_index(drop=True)

    def _is_open(self, dev, ts=None):
        return bool(self._open_mask(dev, pd.DatetimeIndex([ts or self._now()]))[0])

    def get_device_status(self, device_id):
        if device_id in self._offline_since:
            return "Offline"
        if self._is_open(device_id):
            return "Theft detected"
        now = self._now()
        recent = self.get_readings(device_id, now - pd.Timedelta(minutes=10), now, "1min")
        return "Warning" if len(recent) and recent["flagged"].any() else "Normal"

    def get_fleet_overview(self):
        rows, now = [], self._now()
        for dev, d in self._devices.items():
            r = self.get_latest_reading(dev)
            hist = self.get_readings(dev, now - pd.Timedelta(hours=1), now, "5min")
            risk = float(hist["anomaly_score"].mean()) if len(hist) else 0.0
            if self._is_open(dev):
                risk = max(risk, max([e["probability"] for e in self._events
                                      if e["device_id"] == dev and e["status"] == "Confirmed"] or [0.9]))
            n_open = sum(1 for a in self._alerts if a["device_id"] == dev and a["acknowledged_by"] is None)
            rows.append(dict(device_id=dev, location=d["location"], owner=d["owner"],
                             status=self.get_device_status(dev), last_reading=r["timestamp"],
                             voltage=r["voltage"], power_w=r["power"], relay_state=r["relay_state"],
                             theft_risk=round(risk, 2), open_alerts=n_open))
        return pd.DataFrame(rows, columns=FLEET_COLUMNS)

    # ---------------------------------------------------------------- forecast
    def get_forecast(self, device_id, horizon_hours=24, step_minutes=30):
        n = int(horizon_hours * 60 / step_minutes)
        idx = pd.date_range(self._now().ceil(f"{step_minutes}min"), periods=n, freq=f"{step_minutes}min")
        yhat = self._expected(device_id, idx) * 0.98
        width = yhat * (0.08 + 0.10 * np.linspace(0, 1, n))      # interval widens with the horizon
        return pd.DataFrame({"target_time": idx, "yhat": yhat.round(0), "yhat_lower": (yhat - width).round(0),
                             "yhat_upper": (yhat + width).round(0), "model_id": "forecast_prophet_v1.3"})

    def get_forecast_metrics(self, device_id):
        end = self._now().floor("30min") - pd.Timedelta(hours=48)
        idx = pd.date_range(end - pd.Timedelta(hours=24), end, freq="30min")
        actual = self._generate(device_id, idx)["power"].to_numpy()
        yhat = self._expected(device_id, idx) * 0.98
        base = self._generate(device_id, idx - pd.Timedelta(hours=24))["power"].to_numpy()
        mae, rmse = float(np.mean(np.abs(actual - yhat))), float(np.sqrt(np.mean((actual - yhat) ** 2)))
        mae_b = float(np.mean(np.abs(actual - base)))
        return dict(model="Prophet", version="v1.3 (mock)", mae=round(mae, 1), rmse=round(rmse, 1),
                    baseline_mae=round(mae_b, 1), improvement_pct=round(100 * (1 - mae / mae_b), 1),
                    backtest="24 h held-out window, 2 days ago")

    # ---------------------------------------------------------------- alerts & events
    def get_alerts(self, device_ids, start, end):
        rows = [a for a in self._alerts if a["device_id"] in device_ids
                and pd.Timestamp(start) <= a["created_at"] <= pd.Timestamp(end)]
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
                    a.update(acknowledged_by=user, acknowledged_at=self._now().floor("s"), status="Acknowledged")
                    return True, f"Alert {alert_id} acknowledged."
        return False, "Alert not found."

    def get_theft_events(self, device_ids, start, end):
        rows = [e for e in self._events if e["device_id"] in device_ids
                and pd.Timestamp(start) <= e["detected_at"] <= pd.Timestamp(end)]
        df = pd.DataFrame(rows, columns=EVENT_COLUMNS)
        return df.sort_values("detected_at", ascending=False).reset_index(drop=True) if len(df) else df

    # ---------------------------------------------------------------- relay
    def get_relay_state(self, device_id):
        for s, e in self._relay_intervals.get(device_id, []):
            if e is None:
                reason = next((r["reason"] for r in reversed(self._relay_log)
                               if r["device_id"] == device_id and r["action"] == "OPEN"), "")
                return dict(state="OPEN", since=s, reason=reason)
        return dict(state="CLOSED", since=None, reason="")

    def get_relay_log(self, device_ids, start, end):
        rows = [r for r in self._relay_log if r["device_id"] in device_ids
                and pd.Timestamp(start) <= r["time"] <= pd.Timestamp(end)]
        df = pd.DataFrame(rows, columns=RELAY_COLUMNS)
        return df.sort_values("time", ascending=False).reset_index(drop=True) if len(df) else df

    def restore_load(self, device_id, user, reason):
        with self._lock:
            opened = [iv for iv in self._relay_intervals.get(device_id, []) if iv[1] is None]
            if not opened:
                return False, "The relay is already closed."
            now = self._now().floor("s")
            for iv in opened:
                iv[1] = now
            for ev in self._events:
                if ev["device_id"] == device_id and ev["status"] == "Confirmed":
                    ev["status"] = "Restored"
            self._relay_log.append(dict(time=now, device_id=device_id, action="CLOSE",
                                        reason=reason or "Restored after review", user=user))
        return True, f"Restore command issued for {device_id}. The unit will close the relay."

    def simulate_theft(self, device_id, user):
        with self._lock:
            if self._is_open(device_id):
                return False, "Relay is already open for this device."
            now = self._now().floor("min")
            self._theft_windows.setdefault(device_id, []).append(
                (now - pd.Timedelta(minutes=WINDOW_MINUTES * 3), now))
            self._relay_intervals.setdefault(device_id, []).append([now, None])
            ev = self._add_event(device_id, now, "Theft", 0.91, 0.94, "Confirmed", self._thresholds["n_windows"])
            self._add_alert(ev, "Theft confirmed (simulated demo event). Load cut off.")
            self._relay_log.append(dict(time=now, device_id=device_id, action="OPEN",
                                        reason="Confirmed theft (simulated by " + user + ")", user="system"))
        return True, f"Simulated theft on {device_id}: alert raised and load cut off."

    # ---------------------------------------------------------------- models & settings
    def get_model_info(self):
        t = self._now().normalize() - pd.Timedelta(days=9)
        rows = [
            ("forecast_prophet_v1.3", "Usage forecasting", "Prophet", "v1.3", t, 41.0, 55.0, None, None, None,
             "Placeholder metrics (demo data)"),
            ("anomaly_iforest_v1.1", "Anomaly scoring", "Isolation Forest", "v1.1", t, None, None, None, None, None,
             "Unsupervised - no labelled metric"),
            ("theft_clf_v1.2", "Theft classification", "XGBoost + SMOTE", "v1.2", t, None, None, 0.86, 0.82, 0.84,
             "Placeholder metrics (demo data), theft class only")]
        return pd.DataFrame(rows, columns=MODEL_COLUMNS)

    def request_retrain(self, user):
        with self._lock:
            self._retrain_requests.append((self._now().floor("s"), user))
        return "Retraining requested (placeholder). Connect this to your training script."

    def get_thresholds(self):
        return dict(self._thresholds)

    def set_thresholds(self, values):
        with self._lock:
            self._thresholds.update(values)
