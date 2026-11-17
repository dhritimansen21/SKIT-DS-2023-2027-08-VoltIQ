"""Pick a few consumers from the big SGCC dataset and save a small file the dashboard can load fast.

Usage:
    python prepare_sample_data.py path/to/data_set.csv            (4 theft + 4 normal consumers)
    python prepare_sample_data.py path/to/data_set.csv --per-class 3
    python prepare_sample_data.py path/to/data_set.csv --pick CONS_NO_1 CONS_NO_2 ...   (your own choice)

Creates:  data/sample_readings.csv   (device_id, date, kwh)
          data/sample_devices.csv    (device_id, cons_no, location, owner, dataset_flag, registered_on)

Automatic choice (only to make a clear demo - change it with --pick):
  * theft-labelled consumers (FLAG=1) whose consumption fell 50-90 % (half recently, half earlier) but did not stop
  * normal consumers (FLAG=0) with a natural daily variation and a stable long-term level
Both need almost complete data (little missing) so the charts look continuous.
"""
import argparse
import os
import numpy as np
import pandas as pd

OWNERS = ["consumer1", "consumer1", "consumer2", "consumer2"] * 4
OUTLIER_KWH = 500          # a few cells in the dataset are absurd (e.g. 514991 kWh in one day)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--per-class", type=int, default=4)
    ap.add_argument("--pick", nargs="*", help="explicit CONS_NO values to use")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
    a = ap.parse_args()

    df = pd.read_csv(a.csv)
    day_cols = [c for c in df.columns if c not in ("CONS_NO", "FLAG")]
    dates = pd.to_datetime(day_cols, format="%m/%d/%Y")
    X = df[day_cols].astype(float).where(lambda v: v <= OUTLIER_KWH)
    X.columns = dates

    if a.pick:
        chosen = df.index[df["CONS_NO"].isin(a.pick)].tolist()
    else:
        Xt = X.T                                             # days x consumers
        m7 = Xt.rolling(7, min_periods=4).mean()
        base = Xt.shift(7).rolling(90, min_periods=45).median()
        drop = (1 - m7 / base.where(base > 1))               # relative fall of the last 7 days vs the usual level
        flag = df["FLAG"].to_numpy()
        miss = X.isna().mean(axis=1).to_numpy()
        recent_miss = X.iloc[:, -120:].isna().mean(axis=1).to_numpy()
        med = np.nanmedian(X.to_numpy(), axis=1)
        still_on = (Xt.iloc[-14:].mean() > 1).to_numpy()      # consumption did not simply drop to zero
        ok_t = (flag == 1) & (miss < 0.12) & (recent_miss < 0.10) & (med > 3) & still_on
        d_recent = drop.iloc[-45:].max().to_numpy()
        d_older = drop.iloc[-200:-60].max().to_numpy()
        # a drop of 50-90 %: strong enough to matter, but the meter keeps recording
        act = [i for i in np.argsort(-np.nan_to_num(d_recent)) if ok_t[i] and 0.5 <= d_recent[i] <= 0.9][: a.per_class // 2 or 1]
        old = [i for i in np.argsort(-np.nan_to_num(d_older)) if ok_t[i] and 0.5 <= d_older[i] <= 0.9 and i not in act][: a.per_class - len(act)]
        n_blocks = 34
        B = np.nanmean(X.iloc[:, : n_blocks * 30].to_numpy().reshape(len(X), n_blocks, 30), axis=2)
        block_cv = np.nanstd(B, axis=1) / np.maximum(np.nanmean(B, axis=1), 1e-6)
        day_cv = np.nanstd(X.to_numpy(), axis=1) / np.maximum(np.nanmean(X.to_numpy(), axis=1), 1e-6)
        ok_n = (flag == 0) & (miss < 0.08) & (recent_miss < 0.05) & (med > 3) & (med < 25) & (day_cv > 0.15) & (day_cv < 0.6) & ~np.isnan(B).any(axis=1)
        no = [i for i in np.argsort(np.nan_to_num(block_cv, nan=9)) if ok_n[i]][: a.per_class]
        th = act + old
        chosen = [i for pair in zip(th, no) for i in pair]
        print(f"theft meters: {len(act)} with a recent drop + {len(old)} with an older drop; normal meters: {len(no)}")

    devs, rows = [], []
    for k, i in enumerate(chosen, start=1):
        did = f"meter_{k:02d}"
        cons = df.loc[i, "CONS_NO"]
        devs.append(dict(device_id=did, cons_no=cons, location=f"Consumer {cons[:8]}", owner=OWNERS[(k - 1) % len(OWNERS)],
                         dataset_flag="theft" if df.loc[i, "FLAG"] == 1 else "normal",
                         registered_on=dates[0].strftime("%Y-%m-%d")))
        rows.append(pd.DataFrame({"device_id": did, "date": dates, "kwh": X.iloc[i].to_numpy()}))
    os.makedirs(a.out, exist_ok=True)
    pd.DataFrame(devs).to_csv(os.path.join(a.out, "sample_devices.csv"), index=False)
    pd.concat(rows).to_csv(os.path.join(a.out, "sample_readings.csv"), index=False)
    print(pd.DataFrame(devs).to_string(index=False))
    print(f"\nSaved {len(devs)} devices x {len(dates)} days to {a.out}")


if __name__ == "__main__":
    main()
