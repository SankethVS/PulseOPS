"""Runs the whole analysis end-to-end and saves everything into SQLite.

    python run_pipeline.py                # uses data/usage.csv (creates fake data if missing)
    python run_pipeline.py --regenerate   # make fresh fake data first
    python run_pipeline.py --no-llm       # skip the LLM, use built-in explanations
    python run_pipeline.py --csv my.csv   # your own data (timestamp,server,cpu_percent,provisioned_cpus)
"""
import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

import db
import generate_data
from anomaly import detect_anomalies
from config import CURRENCY, HORIZON_HOURS, UPLOADED_CSV, USAGE_CSV
from explain import explain, llm_configured
from forecast import train_and_forecast
from recommend import recommend

REQUIRED = {"timestamp", "server", "cpu_percent", "provisioned_cpus"}
TS = "%Y-%m-%d %H:%M:%S"


def _ts(index_or_series):
    return pd.DatetimeIndex(index_or_series).strftime(TS)


def run(csv_path=USAGE_CSV, use_llm: bool = True, regenerate: bool = False,
        seed: int = 42, verbose: bool = True) -> list[dict]:
    csv_path = Path(csv_path)
    if regenerate or not csv_path.exists():
        generate_data.generate(csv_path, seed=seed)
        if verbose:
            print(f"Generated fake data -> {csv_path}")

    raw = pd.read_csv(csv_path, parse_dates=["timestamp"])
    missing = REQUIRED - set(raw.columns)
    if missing:
        raise ValueError(f"CSV is missing columns: {sorted(missing)}")

    usage_rows, fc_rows, bt_rows, an_rows, recs = [], [], [], [], []
    for server, g in raw.groupby("server"):
        cpus = int(g["provisioned_cpus"].iloc[-1])
        # make sure there is exactly one value per hour (fills small gaps)
        y = (g.set_index("timestamp")["cpu_percent"].sort_index()
             .resample("h").mean().interpolate().clip(0, 100))
        if verbose:
            print(f"-> {server}: {len(y)} hourly rows, {cpus} vCPUs")

        res = train_and_forecast(y, horizon=HORIZON_HOURS)
        anomalies = detect_anomalies(y)
        rec = recommend(server, cpus, y, res["forecast"], res["mae"])
        rec["forecast_mae"] = round(res["mae"], 2)
        rec["baseline_mae"] = round(res["baseline_mae"], 2)
        rec["model_name"] = res["model_name"]
        rec["anomaly_count"] = int(len(anomalies))
        text, source = explain(rec, use_llm)
        rec["explanation"], rec["explanation_source"] = text, source
        rec["data_source"] = "Your uploaded data" if csv_path == UPLOADED_CSV else "Simulated demo data"
        rec["generated_at"] = datetime.now().strftime(TS)
        recs.append(rec)

        usage_rows.append(pd.DataFrame({"server": server, "timestamp": _ts(y.index),
                                        "cpu_percent": y.values.round(2)}))
        fc_rows.append(pd.DataFrame({"server": server, "timestamp": _ts(res["forecast"].index),
                                     "forecast_cpu": res["forecast"].values.round(2)}))
        bt = res["backtest"]
        bt_rows.append(pd.DataFrame({"server": server, "timestamp": _ts(bt.index),
                                     "actual": bt["actual"].values.round(2),
                                     "predicted": bt["predicted"].values.round(2)}))
        if len(anomalies):
            an = anomalies.copy()
            an["timestamp"] = _ts(an["timestamp"])
            an.insert(0, "server", server)
            an_rows.append(an)
        if verbose:
            print(f"   {rec['action']:<8} {cpus} -> {rec['recommended_cpus']} vCPUs | "
                  f"MAE {rec['forecast_mae']} vs baseline {rec['baseline_mae']} | "
                  f"saving {CURRENCY}{rec['monthly_saving']:,.2f}/mo")

    db.save_table(pd.concat(usage_rows), "usage")
    db.save_table(pd.concat(fc_rows), "forecasts")
    db.save_table(pd.concat(bt_rows), "backtest")
    db.save_table(pd.concat(an_rows) if an_rows else
                  pd.DataFrame(columns=["server", "timestamp", "cpu_percent", "deviation"]), "anomalies")
    db.save_table(pd.DataFrame(recs), "recommendations")
    if verbose:
        total = sum(r["monthly_saving"] for r in recs if r["monthly_saving"] > 0)
        print(f"\nDone. Potential savings: {CURRENCY}{total:,.2f}/month. Saved to {db.DB_PATH}")
    return recs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(USAGE_CSV))
    ap.add_argument("--regenerate", action="store_true")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    if not a.no_llm:
        print("LLM explanations:", "ON" if llm_configured() else "OFF (no key set - using templates)")
    run(a.csv, use_llm=not a.no_llm, regenerate=a.regenerate, seed=a.seed)
