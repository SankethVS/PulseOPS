"""Find weird spikes in HISTORY with Isolation Forest.

We first remove the normal daily/weekly pattern (so a busy Monday 11am isn't "weird"),
then let Isolation Forest flag the hours that don't fit.
"""
import pandas as pd
from sklearn.ensemble import IsolationForest


def detect_anomalies(y: pd.Series, contamination: float = 0.005) -> pd.DataFrame:
    df = pd.DataFrame({"cpu": y.values}, index=y.index)
    hour_of_week = df.index.dayofweek * 24 + df.index.hour
    typical = df.groupby(hour_of_week)["cpu"].transform("median")
    df["deviation"] = df["cpu"] - typical

    iso = IsolationForest(n_estimators=200, contamination=contamination, random_state=42)
    flagged = iso.fit_predict(df[["cpu", "deviation"]]) == -1
    out = df[flagged & (df["deviation"] > 0)]  # only upward spikes matter for capacity
    return pd.DataFrame({"timestamp": out.index, "cpu_percent": out["cpu"].round(2).values,
                         "deviation": out["deviation"].round(2).values})
