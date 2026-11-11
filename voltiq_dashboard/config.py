"""Central configuration and constants for the VoltIQ dashboard."""

import os

APP_TITLE = "VoltIQ"
APP_SUBTITLE = "Real-Time Electricity Usage Forecasting & Theft Detection"

REFRESH_SECONDS = 5            # NFR-01: a new reading should appear within ~5 s
WINDOW_MINUTES = 5             # length of one detection window (theft confirmed after N consecutive windows)

# FR-28: detection thresholds an administrator can change
DEFAULT_THRESHOLDS = {
    "anomaly_threshold": 0.60,   # Isolation-Forest style anomaly score above which a reading is flagged
    "theft_prob_tau": 0.80,      # classifier probability needed to count a window as "theft"
    "n_windows": 3,              # consecutive windows above tau needed to confirm theft
}

SEVERITY_ORDER = ["low", "medium", "high", "critical"]
SEVERITY_COLORS = {"low": "#2E7D32", "medium": "#F9A825", "high": "#EF6C00", "critical": "#C62828"}
STATUS_COLORS = {"Normal": "#2E7D32", "Warning": "#F9A825", "Theft detected": "#C62828", "Offline": "#757575"}
RELAY_COLORS = {"CLOSED": "#2E7D32", "OPEN": "#C62828"}

PRIMARY = "#1F5FBF"
ACCENT = "#F28C28"

PAGES_CONSUMER = ["Live Monitoring", "Forecast", "Alerts & Anomalies", "Relay Control", "Reports", "Model Info"]
PAGES_ADMIN = PAGES_CONSUMER + ["Fleet Overview", "Admin Settings"]

# "sample" = your real daily dataset (data/ folder), "mock" = synthetic minute-level demo data
DATA_MODE = os.environ.get("VOLTIQ_DATA_MODE", "sample")
