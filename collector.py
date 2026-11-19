"""collector.py - logs this PC's usage once a minute so the AI has history to learn from.

  python collector.py            start logging (leave it running; Ctrl+C to stop)
  python collector.py --export   convert the log to hourly CSV in the PulseOPS format
                                 -> data/usage_mypc.csv

The forecast needs 16 days (384 hourly readings). The more continuous days, the better.
"""
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from pc_monitor import get_metrics

SERVER = "my-pc"                       # name shown in the dashboard
RAW = Path("data/mypc_raw.csv")        # one row per minute (all metrics)
HOURLY = Path("data/usage_mypc.csv")   # hourly rows: timestamp, server, cpu_percent, provisioned_cpus
INTERVAL = 60                          # seconds between readings
MIN_HOURS = 168 + 168 + 48             # same rule as ingest.py


def export():
    if not RAW.exists():
        sys.exit("No data yet. Run  python collector.py  first and leave it running.")
    df = pd.read_csv(RAW, parse_dates=["timestamp"])
    df["timestamp"] = df["timestamp"].dt.floor("h")
    out = (df.groupby("timestamp")
             .agg(cpu_percent=("cpu_percent", "mean"),
                  provisioned_cpus=("cpu_cores", "first"))
             .reset_index())
    out["cpu_percent"] = out["cpu_percent"].round(2)
    out.insert(1, "server", SERVER)
    HOURLY.parent.mkdir(exist_ok=True)
    out.to_csv(HOURLY, index=False)
    print(f"Saved {len(out)} hourly rows -> {HOURLY}")
    if len(out) < MIN_HOURS:
        print(f"Not enough yet: need {MIN_HOURS} hours (~16 days), you have {len(out)}. Keep collecting.")
    else:
        print("Enough history! In the dashboard: sidebar -> Analyse your own data -> upload this file.")


def collect():
    RAW.parent.mkdir(exist_ok=True)
    is_new = not RAW.exists()
    get_metrics()      # first call only primes the CPU / disk counters
    time.sleep(2)
    print(f"Collecting every {INTERVAL}s into {RAW}  (Ctrl+C to stop)")
    with open(RAW, "a", newline="") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["timestamp", "cpu_percent", "cpu_cores", "ram_percent",
                        "disk_percent", "disk_read_mbps", "disk_write_mbps"])
        try:
            while True:
                m = get_metrics()
                w.writerow([datetime.now().isoformat(timespec="seconds"),
                            m["cpu_percent"], m["cpu_cores"], m["ram_percent"],
                            m["disk_percent"], m["disk_read_mbps"], m["disk_write_mbps"]])
                f.flush()
                time.sleep(INTERVAL)
        except KeyboardInterrupt:
            print("\nStopped. Data is saved.")


if __name__ == "__main__":
    export() if "--export" in sys.argv else collect()
