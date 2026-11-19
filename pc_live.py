"""pc_live.py - live "This PC" panel for Streamlit.

Option A (no edits to your dashboard):  streamlit run pc_live.py
Option B (inside dashboard.py):
    from pc_live import render_live_pc
    ...
    if server == "This PC (live)":
        render_live_pc()
"""
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pc_monitor import get_metrics, get_top_processes

RAW = Path("data/mypc_raw.csv")
MIN_HOURS = 384
MAX_POINTS = 90      # ~3 minutes of history at 2s refresh


def _line_chart(df, cols, title, unit, ymax=None):
    fig = go.Figure()
    for col, name in cols:
        fig.add_trace(go.Scatter(x=df["t"], y=df[col], name=name, mode="lines"))
    fig.update_layout(title=title, height=260, margin=dict(l=10, r=10, t=40, b=10),
                      yaxis_title=unit, legend=dict(orientation="h", y=-0.2))
    if ymax:
        fig.update_yaxes(range=[0, ymax])
    return fig


def _live_block():
    m = get_metrics()
    hist = st.session_state.setdefault("pc_hist", [])
    hist.append({"t": time.strftime("%H:%M:%S"), **m})
    del hist[:-MAX_POINTS]
    df = pd.DataFrame(hist)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CPU", f"{m['cpu_percent']}%", f"{m['cpu_cores']} logical cores", delta_color="off")
    c2.metric("RAM", f"{m['ram_percent']}%", f"{m['ram_used_gb']} / {m['ram_total_gb']} GB", delta_color="off")
    c3.metric("Disk usage", f"{m['disk_percent']}%", f"{m['disk_used_gb']} / {m['disk_total_gb']} GB", delta_color="off")
    c4.metric("Disk I/O", f"R {m['disk_read_mbps']} MB/s", f"W {m['disk_write_mbps']} MB/s", delta_color="off")

    a, b = st.columns(2)
    a.plotly_chart(_line_chart(df, [("cpu_percent", "CPU %"), ("ram_percent", "RAM %")],
                               "CPU and RAM", "%", 100), use_container_width=True)
    b.plotly_chart(_line_chart(df, [("disk_read_mbps", "Read MB/s"), ("disk_write_mbps", "Write MB/s")],
                               "Disk I/O", "MB/s"), use_container_width=True)

    with st.expander("Top processes by memory"):
        st.dataframe(pd.DataFrame(get_top_processes(8)), use_container_width=True, hide_index=True)


# Auto-refresh only this block every 2 seconds (needs Streamlit 1.37+).
if hasattr(st, "fragment"):
    _live_block = st.fragment(run_every=2)(_live_block)


def _history_progress():
    st.subheader("Collected history (for the AI forecast)")
    if not RAW.exists():
        st.info("No history yet. Run `python collector.py` in a terminal and leave it running.")
        return
    df = pd.read_csv(RAW, parse_dates=["timestamp"])
    hours = df["timestamp"].dt.floor("h").nunique()
    st.progress(min(hours / MIN_HOURS, 1.0), text=f"{hours} of {MIN_HOURS} hourly readings (about 16 days)")
    if hours >= MIN_HOURS:
        st.success("Enough history. Run `python collector.py --export`, then upload data/usage_mypc.csv "
                   "in the sidebar under 'Analyse your own data'.")
    daily = df.set_index("timestamp")[["cpu_percent", "ram_percent"]].resample("1h").mean().reset_index()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=daily["timestamp"], y=daily["cpu_percent"], name="CPU %"))
    fig.add_trace(go.Scatter(x=daily["timestamp"], y=daily["ram_percent"], name="RAM %"))
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="% (hourly avg)")
    st.plotly_chart(fig, use_container_width=True)


def render_live_pc():
    st.header("This PC (live)")
    st.caption("Real readings from the computer running this dashboard.")
    _live_block()
    if not hasattr(st, "fragment"):
        st.button("Refresh")
        st.warning("Upgrade Streamlit (pip install -U streamlit) for automatic refresh.")
    _history_progress()


if __name__ == "__main__":
    st.set_page_config(page_title="PulseOPS - This PC", layout="wide")
    render_live_pc()
