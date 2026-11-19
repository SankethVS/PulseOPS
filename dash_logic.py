"""Data logic for the dashboard. No Streamlit/Plotly in here, so it is easy to test."""
import pandas as pd


def hour_label(h) -> str:
    h = int(h) % 24
    return f"{(h + 11) % 12 + 1} {'AM' if h < 12 else 'PM'}"


def _weighted(df: pd.DataFrame, col: str, cpus: pd.Series) -> pd.Series:
    """Fleet-wide utilisation per hour, weighted by each server's vCPU count."""
    w = df["server"].map(cpus)
    g = df.assign(w=w, wx=df[col] * w).groupby("timestamp")[["wx", "w"]].sum()
    return g["wx"] / g["w"]


def merge_events(an: pd.DataFrame) -> pd.DataFrame:
    """Consecutive anomalous hours on one server count as ONE spike event."""
    cols = ["server", "timestamp", "cpu_percent", "deviation", "hours"]
    if an.empty:
        return pd.DataFrame(columns=cols)
    an = an.sort_values(["server", "timestamp"]).copy()
    gap = an.groupby("server")["timestamp"].diff() > pd.Timedelta(hours=1)
    an["event"] = (gap | an["server"].ne(an["server"].shift())).cumsum()
    ev = an.groupby("event").agg(server=("server", "first"), timestamp=("timestamp", "first"),
                                 cpu_percent=("cpu_percent", "max"), deviation=("deviation", "max"),
                                 hours=("timestamp", "size"))
    return ev[cols].sort_values("timestamp").reset_index(drop=True)


def build_fleet(fleet: dict, recs: pd.DataFrame) -> dict:
    cpus = recs.set_index("server")["current_cpus"]
    hist, fc = pd.DataFrame(fleet["history"]), pd.DataFrame(fleet["forecast"])
    an = pd.DataFrame(fleet["anomalies"], columns=["server", "timestamp", "cpu_percent", "deviation"])
    for d in (hist, fc, an):
        d["timestamp"] = pd.to_datetime(d["timestamp"])
    hist_avg = _weighted(hist, "cpu_percent", cpus)
    nxt = _weighted(fc, "forecast_cpu", cpus).iloc[:24]
    mae = float(recs["forecast_mae"].mean())
    return {"hist_avg": hist_avg, "hist_max": hist.groupby("timestamp")["cpu_percent"].max(),
            "nxt": nxt, "lo": (nxt - 2 * mae).clip(0, 100), "hi": (nxt + 2 * mae).clip(0, 100),
            "an": merge_events(an), "data_end": hist_avg.index.max(), "mae": mae}


def summary(recs: pd.DataFrame) -> dict:
    a, n = recs["action"], len(recs)
    now, new = float(recs.monthly_cost_now.sum()), float(recs.monthly_cost_new.sum())
    keep = int((a == "KEEP").sum())
    return {"n": n, "down": int((a == "DOWNSIZE").sum()), "keep": keep, "up": int((a == "UPSIZE").sum()),
            "cpus_now": int(recs.current_cpus.sum()), "cpus_rec": int(recs.recommended_cpus.sum()),
            "cost_now": now, "cost_new": new, "saving": now - new,
            "saving_pct": (now - new) / now * 100 if now else 0.0,
            "healthy_pct": keep / n * 100 if n else 0.0}


def recent_anomalies(fl: dict, days: int = 7) -> pd.DataFrame:
    return fl["an"][fl["an"].timestamp >= fl["data_end"] - pd.Timedelta(days=days)]


def insights(fl: dict, s: dict) -> list[tuple[str, str]]:
    """(icon, text) pairs. Icons: ✅ fine, ⚠️ needs attention."""
    nxt, out = fl["nxt"], []
    pk = nxt.idxmax()
    out.append(("✅", f"Fleet demand peaks around {hour_label(pk.hour)}–{hour_label(pk.hour + 1)} "
                      f"(≈{nxt.max():.0f}% CPU)."))
    roll = nxt.rolling(4).mean().dropna()
    if len(roll):
        end = roll.idxmin()
        start = end - pd.Timedelta(hours=3)
        out.append(("✅", f"Quietest window {hour_label(start.hour)}–{hour_label(end.hour + 1)} "
                          f"(≈{roll.min():.0f}%): the best time to scale down."))
    if s["down"]:
        out.append(("⚠️", f"{s['down']} of {s['n']} servers are over-provisioned and can be reduced."))
    if s["up"]:
        out.append(("⚠️", f"{s['up']} server(s) are forecast to run hot. Add capacity before they slow down."))
    week = recent_anomalies(fl)
    out.append(("⚠️", f"{len(week)} unusual spike(s) in the last 7 days.") if len(week)
               else ("✅", "No unusual patterns in the last 7 days."))
    return out


def latest_anomaly(fl: dict):
    if fl["an"].empty:
        return None
    r = fl["an"].iloc[-1]
    return {"server": r.server, "ts": r.timestamp, "cpu": float(r.cpu_percent),
            "typical": float(r.cpu_percent - r.deviation)}
