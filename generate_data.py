"""Step 1 - Make realistic FAKE server usage data.

Real servers show:
  * a daily rhythm   (busy in the daytime, quiet at night)
  * a weekly rhythm  (quieter weekends)
  * a slow trend     (usage creeps up as the business grows)
  * random spikes    (incidents, traffic bursts)
We recreate all four so the AI has something real to learn.
"""
import argparse
import numpy as np
import pandas as pd
from config import USAGE_CSV

# base = typical quiet-time CPU %, amp = extra CPU % at the daily peak,
# cpus = how many vCPUs the team provisioned, growth = CPU % added over 60 days
SERVERS = {
    "web-01":   {"base": 12, "amp": 14, "cpus": 16, "growth": 3},   # way over-provisioned
    "db-01":    {"base": 22, "amp": 16, "cpus": 16, "growth": 4},   # somewhat over-provisioned
    "api-01":   {"base": 34, "amp": 24, "cpus": 8,  "growth": 4},   # about right
    "batch-01": {"base": 6,  "amp": 8,  "cpus": 32, "growth": 1},   # hugely over-provisioned
    "app-02":   {"base": 48, "amp": 28, "cpus": 4,  "growth": 12},  # UNDER-provisioned, growing
}


def generate(path=USAGE_CSV, days: int = 60, seed: int = 42, start: str = "2026-09-20"):
    rng = np.random.default_rng(seed)
    hours = pd.date_range(start, periods=24 * days, freq="h")
    frames = []
    for name, s in SERVERS.items():
        day_wave = np.clip(np.sin((hours.hour.to_numpy() - 6) / 24 * 2 * np.pi), 0, None)
        weekend = np.where(hours.dayofweek.to_numpy() >= 5, 0.6, 1.0)
        trend = np.linspace(0, s["growth"], len(hours))
        noise = rng.normal(0, 2.5, len(hours))
        cpu = s["base"] + s["amp"] * day_wave * weekend + trend + noise

        # a handful of random 1-2 hour spikes
        for idx in rng.choice(len(hours) - 3, size=6, replace=False):
            cpu[idx: idx + rng.integers(1, 3)] += rng.uniform(30, 50)

        frames.append(pd.DataFrame({
            "timestamp": hours,
            "server": name,
            "cpu_percent": np.clip(cpu, 1, 100).round(2),
            "provisioned_cpus": s["cpus"],
        }))

    out = pd.concat(frames, ignore_index=True)
    path = path if hasattr(path, "parent") else __import__("pathlib").Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    df = generate(days=args.days, seed=args.seed)
    print(f"Created {USAGE_CSV} with {len(df):,} rows for {df.server.nunique()} servers")
