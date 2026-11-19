"""Streamlit dashboard.  Run:  streamlit run dashboard.py
Reads from the FastAPI backend; if the API is offline it falls back to reading SQLite directly,
so the demo still works."""
import os

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

import data_access as da
from config import CURRENCY as CUR

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
GREEN, AMBER, RED, BLUE, GREY = "#2e9e5b", "#e8a317", "#d64545", "#2f6fed", "#8a94a6"
ACTION_COLOR = {"DOWNSIZE": GREEN, "KEEP": GREY, "UPSIZE": RED}

st.set_page_config(page_title="Anveshan - Clear Picture", page_icon="📉", layout="wide")


def fetch(path: str, fallback):
    """Try the API first, then SQLite. Returns (data, source_label)."""
    try:
        r = requests.get(f"{API_URL}{path}", timeout=2)
        r.raise_for_status()
        return r.json(), "API"
    except Exception:
        return fallback(), "SQLite (API offline)"


def to_df(rows, time_cols=("timestamp",)):
    df = pd.DataFrame(rows)
    for c in time_cols:
        if c in df:
            df[c] = pd.to_datetime(df[c])
    return df


# ---------- sidebar ----------
with st.sidebar:
    st.header("Controls")
    regen = st.checkbox("Generate brand-new fake data", value=False)
    if st.button("Re-run analysis"):
        with st.spinner("Training models for every server..."):
            try:
                requests.post(f"{API_URL}/run-pipeline", params={"regenerate": regen}, timeout=600).raise_for_status()
            except Exception:
                import run_pipeline
                run_pipeline.run(regenerate=regen, verbose=False)
        st.rerun()
    st.caption(f"Cost assumption: {CUR}3.5 per vCPU-hour (edit config.py).")

# ---------- load data ----------
recs_raw, source = fetch("/recommendations", da.get_recommendations)
st.title("📉 Anveshan: The Clear Picture")
st.caption("Paying for servers nobody uses - forecast usage, right-size capacity, cut the bill.")

if not recs_raw:
    st.warning("No results yet. Run `python run_pipeline.py` (or press **Re-run analysis**) first.")
    st.stop()

recs = to_df(recs_raw, time_cols=("generated_at",))
st.caption(f"Data source: {source} · model: {recs.model_name.iloc[0]} · "
           f"last run: {recs.generated_at.max():%d %b %Y %H:%M}")

# ---------- KPIs ----------
savings = recs.loc[recs.monthly_saving > 0, "monthly_saving"].sum()
extra = -recs.loc[recs.monthly_saving < 0, "monthly_saving"].sum()
total_now = recs.monthly_cost_now.sum()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Potential monthly savings", f"{CUR}{savings:,.0f}", f"{savings / total_now:.0%} of current bill")
k2.metric("Servers to downsize", int((recs.action == "DOWNSIZE").sum()))
k3.metric("Servers at risk (upsize)", int((recs.action == "UPSIZE").sum()),
          f"+{CUR}{extra:,.0f}/mo to stay safe" if extra else None, delta_color="inverse")
k4.metric("Avg forecast error (MAE)", f"{recs.forecast_mae.mean():.1f}% CPU",
          f"vs {recs.baseline_mae.mean():.1f}% for 'repeat last week'", delta_color="off")

# ---------- fleet overview ----------
st.subheader("Fleet overview")
left, right = st.columns([3, 2])
with left:
    view = recs[["server", "action", "current_cpus", "recommended_cpus", "forecast_peak_util",
                 "forecast_avg_util", "monthly_saving"]].rename(columns={
        "current_cpus": "vCPUs now", "recommended_cpus": "vCPUs advised",
        "forecast_peak_util": "peak % (next 7d)", "forecast_avg_util": "avg % (next 7d)",
        "monthly_saving": "saving $/mo"})
    st.dataframe(view, hide_index=True)
with right:
    fig = go.Figure()
    fig.add_bar(x=recs.server, y=recs.current_cpus, name="Provisioned now", marker_color=GREY)
    fig.add_bar(x=recs.server, y=recs.recommended_cpus, name="Recommended",
                marker_color=[ACTION_COLOR[a] for a in recs.action])
    fig.update_layout(barmode="group", height=320, margin=dict(l=10, r=10, t=30, b=10),
                      title="vCPUs: what you pay for vs what you need", legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig)

# ---------- per-server detail ----------
st.subheader("Server detail")
server = st.selectbox("Choose a server", recs.server.tolist())
rec = recs[recs.server == server].iloc[0]

hist = to_df(fetch(f"/history/{server}?days=14", lambda: da.get_history(server, 14))[0])
fc = to_df(fetch(f"/forecast/{server}", lambda: da.get_forecast(server))[0])
an = to_df(fetch(f"/anomalies/{server}", lambda: da.get_anomalies(server))[0])
bt = to_df(fetch(f"/backtest/{server}", lambda: da.get_backtest(server))[0])

tab1, tab2, tab3 = st.tabs(["Forecast & advice", "Model accuracy", "How it works"])

with tab1:
    colour = ACTION_COLOR[rec.action]
    st.markdown(f"### <span style='color:{colour}'>{rec.action}</span> &nbsp; "
                f"{rec.current_cpus} → {rec.recommended_cpus} vCPUs", unsafe_allow_html=True)
    st.info(rec.explanation + ("" if rec.explanation_source == "llm" else "  \n*(template explanation)*"))

    fig = go.Figure()
    fig.add_scatter(x=hist.timestamp, y=hist.cpu_percent, name="Last 14 days (actual)",
                    line=dict(color=BLUE, width=1.5))
    fig.add_scatter(x=fc.timestamp, y=fc.forecast_cpu, name="Next 7 days (forecast)",
                    line=dict(color=colour, width=2, dash="dash"))
    if len(an):
        recent = an[an.timestamp >= hist.timestamp.min()]
        fig.add_scatter(x=recent.timestamp, y=recent.cpu_percent, mode="markers", name="Anomaly spike",
                        marker=dict(color=RED, size=9, symbol="x"))
    fig.add_hline(y=70, line_dash="dot", line_color=GREEN, annotation_text="target peak 70%")
    fig.add_hline(y=85, line_dash="dot", line_color=RED, annotation_text="risk line 85%")
    fig.update_layout(height=430, yaxis_title="CPU %", yaxis_range=[0, 105],
                      margin=dict(l=10, r=10, t=20, b=10), legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Forecast peak", f"{rec.forecast_peak_util}%")
    m2.metric("Peak + safety margin", f"{rec.safe_peak_util}%")
    m3.metric("Peak after resize", f"{rec.util_after}%")
    m4.metric("Monthly saving", f"{CUR}{rec.monthly_saving:,.0f}")
    st.caption(f"{int(rec.anomaly_count)} unusual spikes detected in the full history (Isolation Forest).")

with tab2:
    st.write("We hid the **last 7 days**, forecast them, then compared with what really happened.")
    fig = go.Figure()
    fig.add_scatter(x=bt.timestamp, y=bt.actual, name="Actual", line=dict(color=BLUE))
    fig.add_scatter(x=bt.timestamp, y=bt.predicted, name="Predicted", line=dict(color=AMBER, dash="dash"))
    fig.update_layout(height=380, yaxis_title="CPU %", margin=dict(l=10, r=10, t=20, b=10),
                      legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig)
    a, b = st.columns(2)
    a.metric(f"{rec.model_name} error (MAE)", f"{rec.forecast_mae}% CPU")
    b.metric("'Repeat last week' error", f"{rec.baseline_mae}% CPU",
             f"{(rec.baseline_mae / rec.forecast_mae - 1):+.0%} error vs the AI", delta_color="off")

with tab3:
    st.markdown("""
1. **Collect** hourly CPU usage per server (simulated here; drop in a real CSV with the same columns).
2. **Forecast** the next 7 days with **XGBoost**, using hour, weekday, usage yesterday, usage last week and recent averages.
3. **Add a safety margin** of 2× the model's measured error, so we never trim too close.
4. **Decide**: size each server so its busiest hour sits near 70% - downsize waste, upsize risk.
5. **Explain** each decision in plain English with an LLM (template fallback if offline).
6. **Spot oddities** with Isolation Forest (red ✕ marks).
""")
