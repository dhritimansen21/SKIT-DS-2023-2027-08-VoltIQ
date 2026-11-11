"""PLUG YOUR TRAINED MODELS IN HERE (all three functions are optional).

Each function receives the DAILY consumption history of one meter and may return a result.
Return None to let the dashboard use its built-in fallback (a simple statistical method).

history : pandas Series of daily kWh, index = date (DatetimeIndex), NaN = missing day.

Example with a saved scikit-learn / XGBoost model (put the file in the models/ folder):

    import joblib, pandas as pd
    _clf = joblib.load("models/theft_classifier.pkl")

    def theft_probability(device_id, history):
        X = build_features(history)                  # MUST be the same feature code you used for training
        return pd.Series(_clf.predict_proba(X)[:, 1], index=X.index)
"""


def forecast(device_id, history, horizon_days):
    """Return DataFrame[target_time, yhat, yhat_lower, yhat_upper] (kWh per day) or None."""
    return None


def theft_probability(device_id, history):
    """Return a Series (index = date, values 0..1) with the theft probability per day, or None."""
    return None


def anomaly_score(device_id, history):
    """Return a Series (index = date, values 0..1) with the anomaly score per day, or None."""
    return None
