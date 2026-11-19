"""Validate a user-uploaded CSV and analyse it. Used by the API (/upload) and as a local fallback."""
import io

import pandas as pd

import run_pipeline
from config import UPLOADED_CSV

REQUIRED = ["timestamp", "server", "cpu_percent", "provisioned_cpus"]
MIN_HOURS = 168 + 168 + 48      # a week to learn from + a week to test + warm-up = 16 days
MAX_SERVERS = 30


def validate_csv(raw: bytes) -> pd.DataFrame:
    """Return a clean DataFrame or raise ValueError with a message a beginner can act on."""
    if not raw or not raw.strip():
        raise ValueError("The file is empty.")
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as e:
        raise ValueError(f"Could not read this as a CSV file ({e}).")
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing column(s): {', '.join(missing)}. "
                         f"Your file needs these headers: {', '.join(REQUIRED)}.")
    df = df[REQUIRED].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    for c in ("cpu_percent", "provisioned_cpus"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    bad = int(df.isna().any(axis=1).sum())
    df = df.dropna()
    if df.empty:
        raise ValueError("No usable rows: check that timestamp, cpu_percent and provisioned_cpus are valid.")
    if (df["provisioned_cpus"] <= 0).any():
        raise ValueError("provisioned_cpus must be a positive number for every row.")
    df["server"] = df["server"].astype(str).str.strip()
    df["cpu_percent"] = df["cpu_percent"].clip(0, 100)
    if df["server"].nunique() > MAX_SERVERS:
        raise ValueError(f"Too many servers ({df['server'].nunique()}). This prototype handles up to {MAX_SERVERS}.")
    short = {s: g["timestamp"].dt.floor("h").nunique() for s, g in df.groupby("server")}
    short = {s: h for s, h in short.items() if h < MIN_HOURS}
    if short:
        worst = ", ".join(f"{s} ({h}h)" for s, h in list(short.items())[:3])
        raise ValueError(f"Not enough history: need at least {MIN_HOURS} hourly readings (16 days) per server. "
                         f"Too short: {worst}.")
    if bad:
        print(f"ingest: dropped {bad} unreadable rows")
    return df


def process_upload(raw: bytes, use_llm: bool = True) -> int:
    """Validate -> save -> run the full pipeline. Returns the number of servers analysed."""
    df = validate_csv(raw)
    UPLOADED_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(UPLOADED_CSV, index=False)
    return len(run_pipeline.run(UPLOADED_CSV, use_llm=use_llm, verbose=False))
