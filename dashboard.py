"""AIOps dark dashboard.   Run:  streamlit run dashboard.py
Reads from the FastAPI backend; if the API is offline it reads SQLite directly."""
import os

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

import dash_logic as dl
import data_access as da
from config import CURRENCY as CUR, USAGE_CSV

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
CYAN, BLUE, PURPLE, GREEN, AMBER, RED = "#22d3ee", "#3b82f6", "#8b5cf6", "#22c55e", "#f59e0b", "#ef4444"
ACTION_COLOR = {"DOWNSIZE": AMBER, "KEEP": GREEN, "UPSIZE": RED}
ACTION_LABEL = {"DOWNSIZE": "Over-provisioned", "KEEP": "Healthy", "UPSIZE": "Needs more capacity"}

st.set_page_config(page_title="AIOps Capacity Planner", page_icon="☁️", layout="wide")

st.markdown("""<style>
.stApp{background:radial-gradient(1200px 600px at 15% -10%,#13245e 0%,#070d28 45%,#030615 100%);}
header[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:1.2rem;max-width:1500px;}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#07102e,#050a1f);border-right:1px solid rgba(80,120,255,.2);}
div[class*="st-key-card"]{background:rgba(16,26,62,.55);border:1px solid rgba(80,120,255,.22);border-radius:16px;padding:14px 16px;box-shadow:0 0 24px rgba(40,80,255,.08);}
.ct{font-weight:700;font-size:1.05rem;margin-bottom:2px;color:#f1f5ff;}
.card{background:rgba(16,26,62,.55);border:1px solid rgba(80,120,255,.22);border-radius:16px;padding:16px 18px;height:100%;}
.card-red{background:linear-gradient(135deg,rgba(120,20,40,.45),rgba(30,10,30,.5));border-color:rgba(239,68,68,.55);}
.card-green{background:linear-gradient(135deg,rgba(10,90,70,.35),rgba(10,30,50,.5));border-color:rgba(34,197,94,.45);}
.kpi{display:flex;align-items:center;gap:14px;}
.kpi .ic{font-size:2.2rem;width:58px;height:58px;display:flex;align-items:center;justify-content:center;border-radius:14px;background:rgba(59,130,246,.15);}
.kpi .val{font-size:2rem;font-weight:800;line-height:1.1;color:#fff;}
.kpi .lbl{color:#a9b6e8;font-size:.9rem;} .kpi .sub{color:#7f8fc9;font-size:.78rem;}
.row{display:flex;gap:8px;margin:7px 0;font-size:.93rem;color:#dbe4ff;}
.big{font-size:1.9rem;font-weight:800;color:#fff;} .green{color:#4ade80;} .red{color:#f87171;} .muted{color:#8b9ad3;font-size:.85rem;}
.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;}
.topbar h2{margin:0;font-size:1.5rem;} .pill{color:#a9b6e8;font-size:.9rem;}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#22c55e;margin-right:6px;box-shadow:0 0 8px #22c55e;}
.bell{position:relative;margin-left:18px;font-size:1.3rem;} .bell b{position:absolute;top:-8px;right:-10px;background:#ef4444;color:#fff;font-size:.68rem;border-radius:10px;padding:0 6px;}
.brand{font-size:1.7rem;font-weight:800;background:linear-gradient(90deg,#22d3ee,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-weight:700;font-size:.78rem;}
</style>""", unsafe_allow_html=True)


# ---------- helpers ----------
def H(s: str) -> str:
    """Collapse multi-line HTML so Streamlit's markdown doesn't treat it as a code block."""
    return " ".join(line.strip() for line in s.strip().splitlines())


def money(x: float) -> str:
    return f"{CUR}{x / 1000:,.1f}K" if abs(x) >= 1000 else f"{CUR}{x:,.0f}"


def fetch(path: str, fallback):
    try:
        r = requests.get(f"{API_URL}{path}", timeout=2)
        r.raise_for_status()
        return r.json()
    except Exception:
        return fallback()


def backend_online() -> bool:
    try:
        return requests.get(f"{API_URL}/health", timeout=1.5).ok
    except Exception:
        return False


def run_action(kind: str, raw: bytes = None, regen: bool = False):
    """Upload a CSV or re-run the demo. Uses the API when it is up, otherwise runs locally.
    Returns (ok, message)."""
    try:
        if kind == "upload":
            r = requests.post(f"{API_URL}/upload", data=raw, headers={"Content-Type": "text/csv"}, timeout=900)
        else:
            r = requests.post(f"{API_URL}/run-pipeline", params={"regenerate": regen}, timeout=900)
        if r.ok:
            return True, "Done"
        try:
            return False, r.json().get("detail", r.text)
        except Exception:
            return False, r.text
    except requests.exceptions.ConnectionError:      # API not running -> do the work locally
        try:
            if kind == "upload":
                import ingest
                ingest.process_upload(raw)
            else:
                import run_pipeline
                run_pipeline.run(regenerate=regen, verbose=False)
            return True, "Done (API was offline, ran locally)"
        except ValueError as e:
            return False, str(e)
    except Exception as e:
        return False, str(e)


def style(fig, height=270, ymax=100):
    fig.update_layout(height=height, margin=dict(l=6, r=6, t=6, b=6), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#c7d2fe"),
                      legend=dict(orientation="h", y=1.14, x=0),
                      xaxis=dict(gridcolor="rgba(120,140,255,.07)"),
                      yaxis=dict(gridcolor="rgba(120,140,255,.12)", range=[0, ymax], ticksuffix="%"))
    return fig


def show(fig):
    st.plotly_chart(fig, config={"displayModeBar": False})


def kpi(icon, value, label, sub=""):
    return H(f'<div class="card"><div class="kpi"><div class="ic">{icon}</div><div>'
             f'<div class="val">{value}</div><div class="lbl">{label}</div><div class="sub">{sub}</div></div></div></div>')


# ---------- load ----------
recs_raw = fetch("/recommendations", da.get_recommendations)
with st.sidebar:
    st.markdown('<div class="brand">☁️ AIOps</div>', unsafe_allow_html=True)
    page = st.radio("Navigate", ["📊 Dashboard", "📈 Forecast", "🔔 Alerts", "💡 Recommendations"],
                    label_visibility="collapsed")
    st.markdown("---")
    API_OK = backend_online()
    colour = "#22c55e" if API_OK else "#f59e0b"
    st.markdown(H(f'<span class="dot" style="background:{colour};box-shadow:0 0 8px {colour}"></span>'
                  f'<b>{"Backend connected" if API_OK else "Backend offline"}</b>'), unsafe_allow_html=True)
    st.caption(API_URL if API_OK else "Showing saved results. Start it with: uvicorn api:app")

    st.markdown("**Analyse your own data**")
    up = st.file_uploader("Usage CSV", type="csv", label_visibility="collapsed",
                          help="Columns: timestamp, server, cpu_percent, provisioned_cpus. Hourly rows, 16+ days per server.")
    if up is not None and st.button("Analyse my data"):
        with st.spinner("Validating and training models..."):
            ok, msg = run_action("upload", raw=up.getvalue())
        if ok:
            st.rerun()
        st.error(msg)
    if USAGE_CSV.exists():
        st.download_button("Download sample CSV", USAGE_CSV.read_bytes(), "sample_usage.csv", "text/csv")

    st.markdown("**Demo data**")
    regen = st.checkbox("Generate new random data")
    if st.button("Re-run on demo data"):
        with st.spinner("Training models for every server..."):
            ok, msg = run_action("demo", regen=regen)
        if ok:
            st.rerun()
        st.error(msg)
    st.markdown(H('<div class="card" style="text-align:center;margin-top:30px">🌿<br><b>Save Green.<br>Spend Smart.</b></div>'),
                unsafe_allow_html=True)

if not recs_raw:
    st.warning("No results yet. Run `python run_pipeline.py` (or press **Re-run analysis**) first.")
    st.stop()

recs = pd.DataFrame(recs_raw)
src = recs.data_source.iloc[0] if "data_source" in recs else "Simulated demo data"
fl = dl.build_fleet(fetch("/fleet", da.get_fleet), recs)
S = dl.summary(recs)
n_alerts = len(dl.recent_anomalies(fl))

st.markdown(H(f'''<div class="topbar"><h2>Server Capacity Planner</h2><div class="pill">
<span class="dot"></span>{src} · data up to {fl["data_end"]:%d %b %Y, %I:%M %p} · model: {recs.model_name.iloc[0]}
<span class="bell">🔔<b>{n_alerts}</b></span></div></div>'''), unsafe_allow_html=True)


# ====================== DASHBOARD ======================
def page_dashboard():
    avg_cpu = fl["hist_avg"].iloc[-24:].mean()
    c = st.columns(4)
    c[0].markdown(kpi("🖥️", S["n"], "Total Servers", f"{S['up']} need more capacity"), unsafe_allow_html=True)
    c[1].markdown(kpi("✅", f"{S['cpus_rec']} <span class='muted'>/ {S['cpus_now']}</span>", "vCPUs Actually Needed",
                      f"{S['cpus_now'] - S['cpus_rec']} vCPUs of waste"), unsafe_allow_html=True)
    c[2].markdown(kpi("⚙️", f"{avg_cpu:.0f}%", "Avg CPU (last 24h)", "weighted by vCPUs"), unsafe_allow_html=True)
    c[3].markdown(kpi("💾", f"{S['saving_pct']:.0f}%", "Potential Savings",
                      f"≈ {money(S['saving'])} / month"), unsafe_allow_html=True)
    st.write("")

    a, b, c3 = st.columns([5, 5, 3.2])
    with a, st.container(key="card_util"):
        st.markdown('<div class="ct">Resource Utilization <span class="muted">(last 48h)</span></div>', unsafe_allow_html=True)
        f = go.Figure()
        f.add_scatter(x=fl["hist_avg"].index, y=fl["hist_avg"].values, name="Fleet avg CPU", fill="tozeroy",
                      line=dict(color=CYAN, width=3, shape="spline"), fillcolor="rgba(34,211,238,.10)")
        f.add_scatter(x=fl["hist_max"].index, y=fl["hist_max"].values, name="Busiest server",
                      line=dict(color=PURPLE, width=2, shape="spline"))
        pk = fl["hist_max"].idxmax()
        f.add_annotation(x=pk, y=fl["hist_max"].max(), text=f"Peak: {fl['hist_max'].max():.0f}%", showarrow=True,
                         arrowcolor=PURPLE, bgcolor="#0b1330", bordercolor=PURPLE, font=dict(color="white"))
        show(style(f, ymax=min(105, max(60, fl["hist_max"].max() * 1.25))))
    with b, st.container(key="card_fc"):
        st.markdown('<div class="ct">Demand Forecast <span class="muted">(next 24h)</span></div>', unsafe_allow_html=True)
        f = go.Figure()
        f.add_scatter(x=fl["hi"].index, y=fl["hi"].values, line=dict(width=0), showlegend=False, hoverinfo="skip")
        f.add_scatter(x=fl["lo"].index, y=fl["lo"].values, line=dict(width=0), fill="tonexty",
                      fillcolor="rgba(59,130,246,.28)", name="Confidence band")
        h24 = fl["hist_avg"].iloc[-24:]
        f.add_scatter(x=h24.index, y=h24.values, name="Historical", line=dict(color="#93c5fd", dash="dash", width=2))
        f.add_scatter(x=fl["nxt"].index, y=fl["nxt"].values, name="Predicted", line=dict(color=CYAN, width=3, shape="spline"))
        show(style(f, ymax=min(100, max(45, fl["hi"].max() * 1.3))))
    with c3:
        rows = "".join(f'<div class="row"><span>{i}</span><span>{t}</span></div>' for i, t in dl.insights(fl, S))
        st.markdown(H(f'<div class="card"><div class="ct">💡 Key Insights</div>{rows}</div>'), unsafe_allow_html=True)

    st.write("")
    a, b, c3 = st.columns([4.5, 5.5, 3.2])
    an = dl.latest_anomaly(fl)
    with a:
        if an:
            body = (f'CPU spiked to <b>{an["cpu"]:.0f}%</b> on <b>{an["server"]}</b> '
                    f'(usually ≈{an["typical"]:.0f}% at that hour)<br><span class="muted">{an["ts"]:%d %b, %I:%M %p} · '
                    f'{n_alerts} spike(s) in the last 7 days</span>')
        else:
            body = "No unusual spikes detected."
        st.markdown(H(f'<div class="card card-red"><div class="ct red">⚠️ Anomaly Detected</div>{body}</div>'),
                    unsafe_allow_html=True)
    with b:
        st.markdown(H(f'''<div class="card card-green"><div class="ct" style="color:#fbbf24">✨ Optimization Recommendation</div>
        <div class="row"><span>✅</span><span>Total vCPUs: <b>{S["cpus_now"]} → {S["cpus_rec"]}</b></span></div>
        <div class="row"><span>✅</span><span>Scale down <b>{S["down"]}</b> server(s), scale up <b>{S["up"]}</b></span></div>
        <div class="row"><span>✅</span><span>Keep <b>{S["keep"]}</b> unchanged</span></div></div>'''),
                    unsafe_allow_html=True)
    with c3, st.container(key="card_snap"):
        pk = fl["nxt"].idxmax()
        st.markdown(H(f'<div class="ct">📊 Forecast Snapshot</div><div class="muted">Next peak</div>'
                      f'<div class="big">≈ {fl["nxt"].max():.0f}%</div><div class="muted">at {dl.hour_label(pk.hour)}</div>'),
                    unsafe_allow_html=True)
        f = go.Figure(go.Scatter(x=fl["nxt"].index, y=fl["nxt"].values, fill="tozeroy",
                                 line=dict(color=PURPLE, width=2, shape="spline"), fillcolor="rgba(139,92,246,.25)"))
        f.update_layout(height=70, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(visible=False), yaxis=dict(visible=False))
        show(f)

    st.write("")
    a, b = st.columns(2)
    with a, st.container(key="card_cost"):
        st.markdown('<div class="ct">Cost Analysis <span class="muted">(per month)</span></div>', unsafe_allow_html=True)
        k1, k2 = st.columns([3, 2])
        f = go.Figure(go.Bar(x=["Current", "Optimized"], y=[S["cost_now"], S["cost_new"]], marker_color=["#6b7bb8", GREEN],
                             text=[money(S["cost_now"]), money(S["cost_new"])], textposition="outside",
                             textfont=dict(color="white")))
        f.update_layout(height=210, margin=dict(l=0, r=0, t=22, b=0), paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#c7d2fe"), yaxis=dict(visible=False, range=[0, S["cost_now"] * 1.25]))
        with k1:
            show(f)
        k2.markdown(H(f'<div class="card" style="margin-top:20px"><b>Estimated Savings</b>'
                      f'<div class="big green">{S["saving_pct"]:.0f}%</div><div class="muted">({money(S["saving"])} with AI)</div></div>'),
                    unsafe_allow_html=True)
    with b, st.container(key="card_status"):
        st.markdown('<div class="ct">Server Status</div>', unsafe_allow_html=True)
        k1, k2 = st.columns([3, 2])
        k1.markdown(H(f'''<div class="row">🟢 <span style="width:120px">Healthy</span><b>{S["keep"]}</b></div>
            <div class="row">🟡 <span style="width:120px">Over-provisioned</span><b>{S["down"]}</b></div>
            <div class="row">🔴 <span style="width:120px">Needs capacity</span><b>{S["up"]}</b></div>'''),
                    unsafe_allow_html=True)
        f = go.Figure(go.Pie(values=[S["keep"], S["down"], S["up"]], hole=0.72, sort=False, textinfo="none",
                             marker=dict(colors=[GREEN, AMBER, RED])))
        f.add_annotation(text=f'<b>{S["healthy_pct"]:.0f}%</b><br>Healthy', x=0.5, y=0.5, xref="paper", yref="paper",
                        showarrow=False, font=dict(size=16, color="white"))
        f.update_layout(height=190, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
        with k2:
            show(f)


# ====================== FORECAST ======================
def page_forecast():
    server = st.selectbox("Server", recs.server.tolist())
    r = recs[recs.server == server].iloc[0]
    hist = pd.DataFrame(fetch(f"/history/{server}?days=14", lambda: da.get_history(server, 14)))
    fc = pd.DataFrame(fetch(f"/forecast/{server}", lambda: da.get_forecast(server)))
    bt = pd.DataFrame(fetch(f"/backtest/{server}", lambda: da.get_backtest(server)))
    for d in (hist, fc, bt):
        d["timestamp"] = pd.to_datetime(d["timestamp"])
    an = fl["an"][fl["an"].server == server]
    with st.container(key="card_f1"):
        st.markdown(f'<div class="ct">{server}: last 14 days and next 7 days</div>', unsafe_allow_html=True)
        f = go.Figure()
        f.add_scatter(x=hist.timestamp, y=hist.cpu_percent, name="Actual", line=dict(color="#93c5fd", width=1.5))
        f.add_scatter(x=fc.timestamp, y=fc.forecast_cpu, name="Forecast", line=dict(color=CYAN, width=2.5, dash="dash"))
        an = an[an.timestamp >= hist.timestamp.min()]
        if len(an):
            f.add_scatter(x=an.timestamp, y=an.cpu_percent, mode="markers", name="Spike",
                          marker=dict(color=RED, size=10, symbol="x"))
        f.add_hline(y=70, line_dash="dot", line_color=GREEN, annotation_text="target peak 70%")
        f.add_hline(y=85, line_dash="dot", line_color=RED, annotation_text="risk 85%")
        show(style(f, 400, 105))
    m = st.columns(4)
    m[0].metric("Forecast peak", f"{r.forecast_peak_util}%")
    m[1].metric("Peak + safety margin", f"{r.safe_peak_util}%")
    m[2].metric(f"{r.model_name} error (MAE)", f"{r.forecast_mae}% CPU")
    m[3].metric("'Repeat last week' error", f"{r.baseline_mae}% CPU")
    with st.container(key="card_f2"):
        st.markdown('<div class="ct">Accuracy test: last 7 days hidden, then predicted</div>', unsafe_allow_html=True)
        f = go.Figure()
        f.add_scatter(x=bt.timestamp, y=bt.actual, name="Actual", line=dict(color="#93c5fd"))
        f.add_scatter(x=bt.timestamp, y=bt.predicted, name="Predicted", line=dict(color=AMBER, dash="dash"))
        show(style(f, 300, 105))


# ====================== ALERTS ======================
def page_alerts():
    ev = fl["an"].sort_values("timestamp", ascending=False).copy()
    st.markdown(f"### 🔔 {len(ev)} spike events found · {n_alerts} in the last 7 days")
    st.caption("Detected by Isolation Forest after removing each server's normal daily/weekly pattern. "
               "Consecutive hours are merged into one event.")
    ev["usual %"] = (ev.cpu_percent - ev.deviation).round(1)
    ev["timestamp"] = ev.timestamp.dt.strftime("%d %b %Y, %H:%M")
    st.dataframe(ev.rename(columns={"timestamp": "started", "cpu_percent": "peak CPU %",
                                    "deviation": "above usual (pts)", "hours": "hours"})
                 [["server", "started", "peak CPU %", "usual %", "above usual (pts)", "hours"]], hide_index=True)


# ====================== RECOMMENDATIONS ======================
def page_reco():
    st.markdown(f"### 💡 Recommendations: save {money(S['saving'])} per month")
    for _, r in recs.sort_values("monthly_saving", ascending=False).iterrows():
        col = ACTION_COLOR[r.action]
        delta = (f'saves <b class="green">{money(r.monthly_saving)}</b>/mo' if r.monthly_saving > 0 else
                 f'costs <b class="red">{money(-r.monthly_saving)}</b> more/mo' if r.monthly_saving < 0 else "no change")
        tag = "" if r.explanation_source == "llm" else " <span class='muted'>(template explanation)</span>"
        st.markdown(H(f'''<div class="card" style="margin-bottom:12px;border-left:4px solid {col}">
            <span class="ct">{r.server}</span> &nbsp;<span class="badge" style="background:{col}33;color:{col}">{r.action} · {ACTION_LABEL[r.action]}</span>
            <div class="big" style="font-size:1.3rem">{r.current_cpus} → {r.recommended_cpus} vCPUs &nbsp;<span class="muted">{delta}</span></div>
            <div class="muted">Forecast peak {r.forecast_peak_util}% · average {r.forecast_avg_util}% · peak after resize {r.util_after}%</div>
            <div style="margin-top:8px">{r.explanation}{tag}</div></div>'''), unsafe_allow_html=True)


{"📊 Dashboard": page_dashboard, "📈 Forecast": page_forecast,
 "🔔 Alerts": page_alerts, "💡 Recommendations": page_reco}[page]()
