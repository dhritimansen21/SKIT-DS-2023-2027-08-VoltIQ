import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

dff = pd.read_csv("data set.csv")

date_cols = dff.columns.difference(["CONS_NO", "FLAG"])

dff["MISSING_PERCENT"] = dff[date_cols].isna().mean(axis=1) * 100

dff = dff[dff["MISSING_PERCENT"] < 50].copy()

print("Customers remaining:", len(dff))

dff[date_cols] = dff[date_cols].interpolate(
    axis=1,
    limit_direction="both"
)

print("Missing values remaining:",
      dff[date_cols].isna().sum().sum())

dff["AVG_CONSUMPTION"] = dff[date_cols].mean(axis=1)
dff["STD_CONSUMPTION"] = dff[date_cols].std(axis=1)
dff["MIN_CONSUMPTION"] = dff[date_cols].min(axis=1)
dff["MAX_CONSUMPTION"] = dff[date_cols].max(axis=1)
dff["MEDIAN_CONSUMPTION"] = dff[date_cols].median(axis=1)

dff["ZERO_DAYS"] = (dff[date_cols] == 0).sum(axis=1)

dff["ZERO_PERCENT"] = (
    (dff[date_cols] == 0).mean(axis=1) * 100
)

features = [
    "AVG_CONSUMPTION",
    "STD_CONSUMPTION",
    "MIN_CONSUMPTION",
    "MAX_CONSUMPTION",
    "MEDIAN_CONSUMPTION",
    "ZERO_DAYS",
    "ZERO_PERCENT",
    "MISSING_PERCENT"
]



X = dff[features]
y = dff["FLAG"]

from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)


from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix

model = RandomForestClassifier(
    n_estimators=200,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1
)

model.fit(X_train, y_train)

y_pred = model.predict(X_test)

print("Confusion Matrix:")
print(confusion_matrix(y_test, y_pred))

print("\nClassification Report:")
print(classification_report(y_test, y_pred))