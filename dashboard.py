"""AIOps dark dashboard.   Run:  streamlit run dashboard.py
Reads from the FastAPI backend; if the API is offline it reads SQLite directly."""
import os

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

import cost_opt as co
import dash_logic as dl
import explain as ex
import data_access as da
from config import CURRENCY as CUR, USAGE_CSV
from fmt import inr, inr_ticks

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
.card-save{background:linear-gradient(135deg,rgba(10,110,70,.40),rgba(8,30,50,.55));border-color:rgba(34,197,94,.5);}
.card-warn{border-color:rgba(245,158,11,.55);} .orange{color:#fbbf24;}
.banner{background:linear-gradient(90deg,rgba(16,185,129,.22),rgba(59,130,246,.18));border:1px solid rgba(34,197,94,.45);border-radius:16px;padding:14px 18px;margin-bottom:12px;}
.banner h3{margin:0;color:#fff;} .tag-sim{display:inline-block;background:rgba(245,158,11,.15);color:#fbbf24;border:1px solid rgba(245,158,11,.4);border-radius:8px;padding:1px 8px;font-size:.75rem;}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-weight:700;font-size:.78rem;}
</style>""", unsafe_allow_html=True)


# ---------- helpers ----------
def H(s: str) -> str:
    """Collapse multi-line HTML so Streamlit's markdown doesn't treat it as a code block."""
    return " ".join(line.strip() for line in s.strip().splitlines())


def money(x: float) -> str:
    """Indian format (Thousand / Lakhs / Crores). Display only; see fmt.py."""
    return inr(x, CUR)


def money_axis(fig, vmin, vmax, axis="y"):
    vals, txt = inr_ticks(vmin, vmax)
    (fig.update_yaxes if axis == "y" else fig.update_xaxes)(tickvals=vals, ticktext=txt)
    return fig


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


def sev(v):
    return GREEN if v < 70 else AMBER if v < 85 else RED


def style(fig, height=270, ymax=100):
    ax = dict(gridcolor="rgba(120,140,255,.10)", zeroline=False, linecolor="rgba(120,140,255,.25)",
              tickfont=dict(size=11, color="#9fb0e8"))
    fig.update_layout(height=height, margin=dict(l=6, r=6, t=26, b=6), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#c7d2fe", family="Inter, sans-serif"),
                      hovermode="x unified", hoverlabel=dict(bgcolor="#0b1330", font_color="#fff"),
                      legend=dict(orientation="h", y=1.15, x=0, font=dict(size=12)),
                      xaxis=dict(ax, tickformat="%d %b\n%H:%M", showspikes=True, spikecolor="#5b6fb8", spikethickness=1),
                      yaxis=dict(ax, range=[0, ymax], ticksuffix="%"))
    return fig


def zones(fig):
    """Faint green / amber / red bands so people instantly see what is OK."""
    for y0, y1, c in ((0, 70, "34,197,94"), (70, 85, "245,158,11"), (85, 100, "239,68,68")):
        fig.add_hrect(y0=y0, y1=y1, fillcolor=f"rgba({c},.05)", line_width=0, layer="below")
    return fig


def show(fig):
    st.plotly_chart(fig, config={"displayModeBar": False})


def kpi(icon, value, label, sub=""):
    return H(f'<div class="card"><div class="kpi"><div class="ic">{icon}</div><div>'
             f'<div class="val">{value}</div><div class="lbl">{label}</div><div class="sub">{sub}</div></div></div></div>')



def gauge(val, prev, title, key):
    f = go.Figure(go.Indicator(
        mode="gauge+number+delta", value=val, number=dict(suffix="%", font=dict(size=34, color="white"), valueformat=".0f"),
        delta=dict(reference=prev, valueformat=".0f", suffix="%", increasing=dict(color=RED), decreasing=dict(color=GREEN)),
        title=dict(text=title, font=dict(size=15, color="#c7d2fe")),
        gauge=dict(axis=dict(range=[0, 100], tickwidth=0, tickfont=dict(size=9, color="#7f8fc9")),
                   bar=dict(color=sev(val), thickness=0.32), bgcolor="rgba(0,0,0,0)", borderwidth=0,
                   steps=[dict(range=[0, 70], color="rgba(34,197,94,.14)"), dict(range=[70, 85], color="rgba(245,158,11,.18)"),
                          dict(range=[85, 100], color="rgba(239,68,68,.22)")],
                   threshold=dict(line=dict(color="white", width=3), thickness=0.8, value=val))))
    f.update_layout(height=190, margin=dict(l=18, r=18, t=38, b=0), paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#c7d2fe"))
    return f


def dbtn(kind, tag=""):
    """Small 'Details' button; opens the pop-up for that card."""
    if st.button("🔍 Details", key=f"btn_{kind}{tag}", use_container_width=True):
        detail_dialog(kind)


@st.cache_data(ttl=60, show_spinner=False)
def server_hist(servers: tuple, days: int = 2):
    out = []
    for s_ in servers:
        d = pd.DataFrame(fetch(f"/history/{s_}?days={days}", lambda s_=s_: da.get_history(s_, days)))
        d["server"] = s_
        out.append(d)
    d = pd.concat(out)
    d["timestamp"] = pd.to_datetime(d["timestamp"])
    return d


def note(txt):
    st.markdown(f'<div class="muted" style="margin:4px 0 10px">💬 {txt}</div>', unsafe_allow_html=True)


@st.dialog("🔍 Details", width="large")
def detail_dialog(kind):
    RES = dl.resources(fl["hist_avg"])
    if kind in RES:                                           # ---- CPU / Memory / IO / Disk ----
        ic, name, expl = dl.RES_META[kind]
        s_ = RES[kind]
        st.markdown(f"#### {ic} {name}")
        note(expl + ("" if kind == "cpu" else " <i>(Simulated from CPU: your data only has CPU.)</i>"))
        m = st.columns(4)
        m[0].metric("Now", f"{s_.iloc[-1]:.0f}%", f"{s_.iloc[-1] - s_.iloc[-25]:+.0f}% vs 24h ago", delta_color="inverse")
        m[1].metric("Average (48h)", f"{s_.mean():.0f}%")
        m[2].metric("Peak (48h)", f"{s_.max():.0f}%", f"at {s_.idxmax():%d %b %H:%M}", delta_color="off")
        m[3].metric("Lowest (48h)", f"{s_.min():.0f}%")
        f = zones(go.Figure())
        f.add_scatter(x=s_.index, y=s_.values, name=name, fill="tozeroy", fillcolor="rgba(34,211,238,.10)",
                      line=dict(color=CYAN, width=3, shape="spline"), hovertemplate="%{y:.1f}%")
        f.add_scatter(x=[s_.idxmax()], y=[s_.max()], mode="markers+text", text=[f"Peak {s_.max():.0f}%"], textposition="top center",
                      marker=dict(color=RED, size=11, line=dict(color="white", width=2)), showlegend=False, hoverinfo="skip")
        f.add_scatter(x=[s_.index[-1]], y=[s_.iloc[-1]], mode="markers", name="Now",
                      marker=dict(color=sev(s_.iloc[-1]), size=13, line=dict(color="white", width=2)))
        st.markdown('<div class="ct">Last 48 hours</div>', unsafe_allow_html=True)
        st.plotly_chart(style(f, 300, min(105, max(60, s_.max() * 1.3))), config={"displayModeBar": False})
        c1, c2 = st.columns(2)
        prof = s_.groupby(s_.index.hour).mean()
        with c1:
            st.markdown('<div class="ct">Typical day (avg by hour)</div>', unsafe_allow_html=True)
            f = go.Figure(go.Bar(x=[dl.hour_label(h) for h in prof.index], y=prof.values, marker_color=[sev(v) for v in prof.values],
                                 hovertemplate="%{x}: %{y:.0f}%<extra></extra>"))
            st.plotly_chart(style(f, 240, 100).update_layout(xaxis=dict(tickangle=-60, tickfont=dict(size=9)), hovermode="closest"),
                            config={"displayModeBar": False})
        with c2:
            st.markdown('<div class="ct">How much time at each level</div>', unsafe_allow_html=True)
            bins = pd.cut(s_, [0, 70, 85, 100], labels=["Healthy <70%", "Busy 70-85%", "Critical >85%"]).value_counts().sort_index()
            f = go.Figure(go.Pie(labels=bins.index, values=bins.values, hole=.62, sort=False, marker=dict(colors=[GREEN, AMBER, RED]),
                                 textinfo="percent"))
            f.update_layout(height=240, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#c7d2fe"),
                            legend=dict(orientation="h", y=-0.05))
            st.plotly_chart(f, config={"displayModeBar": False})
        if kind == "cpu":
            st.markdown('<div class="ct">Which server is busiest right now?</div>', unsafe_allow_html=True)
            last = server_hist(tuple(recs.server)).sort_values("timestamp").groupby("server").cpu_percent.last().sort_values()
            f = go.Figure(go.Bar(y=last.index, x=last.values, orientation="h", marker_color=[sev(v) for v in last.values],
                                 text=[f"{v:.0f}%" for v in last.values], textposition="outside", textfont=dict(color="white")))
            st.plotly_chart(style(f, 60 + 28 * len(last), 100).update_layout(xaxis=dict(range=[0, 105], ticksuffix="%", gridcolor="rgba(120,140,255,.1)"),
                            yaxis=dict(range=None, tickfont=dict(size=11)), hovermode="closest"), config={"displayModeBar": False})
    elif kind == "util":                                      # ---- heat-map per server ----
        st.markdown("#### 🌡️ CPU heat-map: every server, last 48h")
        note("Each row is a server, each column an hour. <b>Green = relaxed, amber = busy, red = hot.</b> Look for rows that are always dark (wasted) or red (at risk).")
        d = server_hist(tuple(recs.server)).pivot_table(index="server", columns="timestamp", values="cpu_percent")
        f = go.Figure(go.Heatmap(z=d.values, x=d.columns, y=d.index, zmin=0, zmax=100, xgap=1, ygap=2,
                                 colorscale=[[0, "#0f3d2e"], [.5, "#22c55e"], [.7, "#f59e0b"], [1, "#ef4444"]],
                                 colorbar=dict(ticksuffix="%", thickness=10), hovertemplate="%{y}<br>%{x|%d %b %H:%M}: %{z:.0f}%<extra></extra>"))
        st.plotly_chart(style(f, 80 + 30 * len(d), 100).update_layout(yaxis=dict(range=None), hovermode="closest"),
                        config={"displayModeBar": False})
        avg = d.mean(axis=1).sort_values()
        f = go.Figure(go.Bar(x=avg.index, y=avg.values, marker_color=[sev(v) for v in avg.values], text=[f"{v:.0f}%" for v in avg.values],
                             textposition="outside", textfont=dict(color="white")))
        st.markdown('<div class="ct">Average CPU per server</div>', unsafe_allow_html=True)
        st.plotly_chart(style(f, 260, 100).update_layout(hovermode="closest"), config={"displayModeBar": False})
    elif kind == "fc":                                        # ---- forecast ----
        st.markdown("#### 🔮 Demand forecast: next 24h")
        note("Solid line = what we expect. Shaded band = likely range (±2× the model's average error).")
        pk = fl["nxt"].idxmax()
        f = zones(go.Figure())
        h = fl["hist_avg"].iloc[-24:]
        f.add_scatter(x=fl["hi"].index, y=fl["hi"].values, line=dict(width=0), showlegend=False, hoverinfo="skip")
        f.add_scatter(x=fl["lo"].index, y=fl["lo"].values, line=dict(width=0), fill="tonexty", fillcolor="rgba(59,130,246,.30)", name="Likely range")
        f.add_scatter(x=h.index, y=h.values, name="Last 24h (actual)", line=dict(color="#93c5fd", width=2, dash="dash"))
        f.add_scatter(x=fl["nxt"].index, y=fl["nxt"].values, name="Predicted", line=dict(color=CYAN, width=3, shape="spline"))
        f.add_scatter(x=[pk], y=[fl["nxt"].max()], mode="markers+text", text=[f"Peak {fl['nxt'].max():.0f}% @ {dl.hour_label(pk.hour)}"],
                      textposition="top center", marker=dict(color=PURPLE, size=11, line=dict(color="white", width=2)), showlegend=False)
        f.add_shape(type="line", x0=h.index[-1], x1=h.index[-1], y0=0, y1=1, yref="paper", line=dict(color="white", dash="dot", width=1))
        f.add_annotation(x=h.index[-1], y=1, yref="paper", text="now", showarrow=False, font=dict(color="white"))
        st.plotly_chart(style(f, 330, min(100, max(50, fl["hi"].max() * 1.3))), config={"displayModeBar": False})
        st.markdown('<div class="ct">Forecast peak per server (next 7 days)</div>', unsafe_allow_html=True)
        r_ = recs.sort_values("forecast_peak_util")
        f = go.Figure(go.Bar(x=r_.server, y=r_.forecast_peak_util, marker_color=[sev(v) for v in r_.forecast_peak_util],
                             text=[f"{v:.0f}%" for v in r_.forecast_peak_util], textposition="outside", textfont=dict(color="white")))
        f.add_hline(y=70, line_dash="dot", line_color=GREEN, annotation_text="target 70%")
        f.add_hline(y=85, line_dash="dot", line_color=RED, annotation_text="risk 85%")
        st.plotly_chart(style(f, 280, 110).update_layout(hovermode="closest"), config={"displayModeBar": False})
    elif kind in ("servers", "vcpu", "status"):               # ---- servers / vCPUs / status ----
        st.markdown("#### 🖥️ Servers: now vs recommended")
        note("Grey = vCPUs you pay for today. Coloured = what the AI says you need. <b>Amber = shrink, red = grow, green = keep.</b>")
        r_ = recs.sort_values("current_cpus", ascending=False)
        f = go.Figure()
        f.add_bar(x=r_.server, y=r_.current_cpus, name="Current vCPUs", marker_color="#6b7bb8")
        f.add_bar(x=r_.server, y=r_.recommended_cpus, name="Recommended", marker_color=[ACTION_COLOR[a] for a in r_.action],
                  text=r_.recommended_cpus, textposition="outside", textfont=dict(color="white"))
        st.plotly_chart(style(f, 320, r_.current_cpus.max() * 1.25).update_layout(barmode="group", hovermode="x unified",
                        yaxis=dict(ticksuffix="", range=[0, r_.current_cpus.max() * 1.25], gridcolor="rgba(120,140,255,.1)")),
                        config={"displayModeBar": False})
        t = r_[["server", "action", "current_cpus", "recommended_cpus", "forecast_peak_util", "util_after", "monthly_saving"]].copy()
        t["action"] = t.action.map(ACTION_LABEL)
        t["monthly_saving"] = t.monthly_saving.map(money)
        st.dataframe(t.rename(columns={"current_cpus": "now", "recommended_cpus": "recommended", "forecast_peak_util": "peak %",
                                       "util_after": "peak % after", "monthly_saving": "saving / month"}), hide_index=True)
    elif kind in ("saving", "cost"):                          # ---- cost ----
        st.markdown("#### 💰 Where the money goes")
        note(f"Green bar = money saved by resizing. Red bar = extra cost to add capacity. Net saving: <b>{money(S['saving'])}/month</b>.")
        r_ = recs.sort_values("monthly_saving")
        f = go.Figure(go.Bar(y=r_.server, x=r_.monthly_saving, orientation="h", marker_color=[GREEN if v >= 0 else RED for v in r_.monthly_saving],
                             text=[money(v) for v in r_.monthly_saving], textposition="outside", textfont=dict(color="white")))
        money_axis(style(f, 80 + 30 * len(r_), 100).update_layout(xaxis=dict(ticksuffix="", gridcolor="rgba(120,140,255,.1)"),
                        yaxis=dict(range=None), hovermode="closest"), min(0, r_.monthly_saving.min()), max(1, r_.monthly_saving.max() * 1.3), "x")
        f.update_traces(hovertemplate="%{y}: %{text}<extra></extra>")
        st.plotly_chart(f, config={"displayModeBar": False})
        c = r_.sort_values("monthly_saving", ascending=False)
        f = go.Figure(go.Waterfall(x=["Current"] + c.server.tolist() + ["Optimized"], measure=["absolute"] + ["relative"] * len(c) + ["total"],
                                   y=[S["cost_now"]] + (-c.monthly_saving).tolist() + [0], increasing=dict(marker_color=RED),
                                   decreasing=dict(marker_color=GREEN), totals=dict(marker_color=CYAN),
                                   text=[money(S["cost_now"])] + [money(-v) for v in c.monthly_saving] + [money(S["cost_new"])],
                                   textposition="outside", hoverinfo="x+text"))
        st.markdown('<div class="ct">From current bill to optimized bill</div>', unsafe_allow_html=True)
        st.plotly_chart(money_axis(style(f, 300, S["cost_now"] * 1.1).update_layout(yaxis=dict(ticksuffix="", range=[0, S["cost_now"] * 1.1],
                        gridcolor="rgba(120,140,255,.1)"), hovermode="closest"), 0, S["cost_now"] * 1.1), config={"displayModeBar": False})
    elif kind == "anom":                                      # ---- anomalies ----
        st.markdown("#### ⚠️ Unusual spikes")
        note("A spike = CPU far above that server's normal level for that hour of the week.")
        ev = fl["an"]
        if ev.empty:
            st.success("No unusual spikes detected.")
            return
        f = go.Figure(go.Scatter(x=ev.timestamp, y=ev.server, mode="markers", marker=dict(size=ev.deviation.clip(8, 40), color=ev.cpu_percent,
                      colorscale=[[0, AMBER], [1, RED]], showscale=True, colorbar=dict(title="CPU %", thickness=10), line=dict(color="white", width=1)),
                      hovertemplate="%{y}<br>%{x|%d %b %H:%M}<extra></extra>"))
        st.plotly_chart(style(f, 80 + 30 * ev.server.nunique(), 100).update_layout(yaxis=dict(range=None), hovermode="closest"),
                        config={"displayModeBar": False})
        cnt = ev.server.value_counts()
        st.plotly_chart(style(go.Figure(go.Bar(x=cnt.index, y=cnt.values, marker_color=AMBER)), 220, cnt.max() * 1.3).update_layout(
            yaxis=dict(ticksuffix="", range=[0, cnt.max() * 1.3]), hovermode="closest"), config={"displayModeBar": False})
        st.caption("Bubble size = how far above normal. Bottom chart = spike count per server.")


# ---------- load ----------
recs_raw = fetch("/recommendations", da.get_recommendations)
with st.sidebar:
    st.markdown('<div class="brand">☁️ AIOps</div>', unsafe_allow_html=True)
    page = st.radio("Navigate", ["📊 Dashboard", "💰 Cost Optimization", "📈 Forecast", "🔔 Alerts", "💡 Recommendations"],
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
    RES = dl.resources(fl["hist_avg"])
    c = st.columns(4)
    c[0].markdown(kpi("🖥️", S["n"], "Total Servers", f"{S['up']} need more capacity"), unsafe_allow_html=True)
    with c[0]:
        dbtn("servers")
    c[1].markdown(kpi("✅", f"{S['cpus_rec']} <span class='muted'>/ {S['cpus_now']}</span>", "vCPUs Actually Needed",
                      f"{S['cpus_now'] - S['cpus_rec']} vCPUs of waste"), unsafe_allow_html=True)
    with c[1]:
        dbtn("vcpu")
    c[2].markdown(kpi("⚙️", f"{avg_cpu:.0f}%", "Avg CPU (last 24h)", "weighted by vCPUs"), unsafe_allow_html=True)
    with c[2]:
        dbtn("cpu", "_kpi")
    c[3].markdown(kpi("💾", f"{S['saving_pct']:.0f}%", "Potential Savings",
                      f"≈ {money(S['saving'])} / month"), unsafe_allow_html=True)
    with c[3]:
        dbtn("saving")
    st.write("")

    st.write("")
    with st.container(key="card_cost"):
        st.markdown('<div class="ct">Cost Analysis <span class="muted">(per month)</span></div>', unsafe_allow_html=True)
        k1, k2 = st.columns([3, 1.4])
        f = go.Figure(go.Bar(x=["Current", "Optimized"], y=[S["cost_now"], S["cost_new"]], marker_color=["#6b7bb8", GREEN], width=0.5, hovertemplate="%{x}: %{text}<extra></extra>",
                             text=[money(S["cost_now"]), money(S["cost_new"])], textposition="outside",
                             textfont=dict(color="white")))
        f.update_layout(height=210, margin=dict(l=0, r=0, t=22, b=0), paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#c7d2fe"), yaxis=dict(visible=False, range=[0, S["cost_now"] * 1.25]))
        with k1:
            show(f)
        k2.markdown(H(f'<div class="card" style="margin-top:20px"><b>Estimated Savings</b>'
                      f'<div class="big green">{S["saving_pct"]:.0f}%</div><div class="muted">({money(S["saving"])} with AI)</div></div>'),
                    unsafe_allow_html=True)
        dbtn("cost")

    st.write("")
    st.markdown('<div class="ct">Live Resource Health <span class="muted">(CPU measured · Memory, I/O, Disk simulated from CPU)</span></div>', unsafe_allow_html=True)
    g = st.columns(4)
    for col_, k in zip(g, ("cpu", "mem", "io", "disk")):
        with col_, st.container(key=f"card_g_{k}"):
            ic, nm, _ = dl.RES_META[k]
            st.plotly_chart(gauge(RES[k].iloc[-1], RES[k].iloc[-25], f"{ic} {nm}", k), config={"displayModeBar": False})
            dbtn(k)
    st.write("")
    st.write("")
    a, b, c3 = st.columns([5, 5, 3.2])
    with a, st.container(key="card_util"):
        st.markdown('<div class="ct">Resource Utilization <span class="muted">(last 48h)</span></div>', unsafe_allow_html=True)
        f = zones(go.Figure())
        f.add_scatter(x=fl["hist_avg"].index, y=fl["hist_avg"].values, name="Fleet avg CPU", fill="tozeroy",
                      line=dict(color=CYAN, width=3, shape="spline"), fillcolor="rgba(34,211,238,.10)")
        f.add_scatter(x=fl["hist_max"].index, y=fl["hist_max"].values, name="Busiest server",
                      line=dict(color=PURPLE, width=2, shape="spline"))
        pk = fl["hist_max"].idxmax()
        f.add_annotation(x=pk, y=fl["hist_max"].max(), text=f"Peak: {fl['hist_max'].max():.0f}%", showarrow=True,
                         arrowcolor=PURPLE, bgcolor="#0b1330", bordercolor=PURPLE, font=dict(color="white"))
        show(style(f, ymax=min(105, max(60, fl["hist_max"].max() * 1.25))))
        dbtn("util")
    with b, st.container(key="card_fc"):
        st.markdown('<div class="ct">Demand Forecast <span class="muted">(next 24h)</span></div>', unsafe_allow_html=True)
        f = zones(go.Figure())
        f.add_scatter(x=fl["hi"].index, y=fl["hi"].values, line=dict(width=0), showlegend=False, hoverinfo="skip")
        f.add_scatter(x=fl["lo"].index, y=fl["lo"].values, line=dict(width=0), fill="tonexty",
                      fillcolor="rgba(59,130,246,.30)", name="Likely range")
        h24 = fl["hist_avg"].iloc[-24:]
        f.add_scatter(x=h24.index, y=h24.values, name="Historical", line=dict(color="#93c5fd", dash="dash", width=2))
        f.add_scatter(x=fl["nxt"].index, y=fl["nxt"].values, name="Predicted", line=dict(color=CYAN, width=3, shape="spline"))
        show(style(f, ymax=min(100, max(45, fl["hi"].max() * 1.3))))
        dbtn("fc")
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
        dbtn("anom")
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
    with a, st.container(key="card_status"):
        st.markdown('<div class="ct">Server Status</div>', unsafe_allow_html=True)
        k1, k2 = st.columns([3, 2])
        k1.markdown(H(f'''<div class="row">🟢 <span style="width:120px">Healthy</span><b>{S["keep"]}</b></div>
            <div class="row">🟡 <span style="width:120px">Over-provisioned</span><b>{S["down"]}</b></div>
            <div class="row">🔴 <span style="width:120px">Needs capacity</span><b>{S["up"]}</b></div>'''),
                    unsafe_allow_html=True)
        f = go.Figure(go.Pie(values=[S["keep"], S["down"], S["up"]], hole=0.72, sort=False, textinfo="none",
                             marker=dict(colors=[GREEN, AMBER, RED], line=dict(color="#070d28", width=3)),
                             labels=["Healthy", "Over-provisioned", "Needs capacity"], hoverinfo="label+value"))
        f.add_annotation(text=f'<b>{S["healthy_pct"]:.0f}%</b><br>Healthy', x=0.5, y=0.5, xref="paper", yref="paper",
                        showarrow=False, font=dict(size=16, color="white"))
        f.update_layout(height=190, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
        with k2:
            show(f)
        dbtn("status")


    with b:
        top = recs.sort_values("monthly_saving", ascending=False).iloc[0]
        st.markdown(H(f'<div class="card card-save"><div class="ct">💰 Cost Optimization</div>'
                      f'<div class="muted">Biggest saving: <b>{top.server}</b> ({top.current_cpus} → {top.recommended_cpus} vCPUs)</div>'
                      f'<div class="big green">{money(top.monthly_saving)}</div>'
                      f'<div class="muted">per month · open <b>Cost Optimization</b> in the sidebar for AI explanations</div></div>'),
                    unsafe_allow_html=True)


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
        expl = r.explanation if r.explanation_source == "llm" else ex.template_explanation(r.to_dict())
        tag = "" if r.explanation_source == "llm" else " <span class='muted'>(template explanation)</span>"
        st.markdown(H(f'''<div class="card" style="margin-bottom:12px;border-left:4px solid {col}">
            <span class="ct">{r.server}</span> &nbsp;<span class="badge" style="background:{col}33;color:{col}">{r.action} · {ACTION_LABEL[r.action]}</span>
            <div class="big" style="font-size:1.3rem">{r.current_cpus} → {r.recommended_cpus} vCPUs &nbsp;<span class="muted">{delta}</span></div>
            <div class="muted">Forecast peak {r.forecast_peak_util}% · average {r.forecast_avg_util}% · peak after resize {r.util_after}%</div>
            <div style="margin-top:8px">{expl}{tag}</div></div>'''), unsafe_allow_html=True)


# ====================== COST OPTIMIZATION ======================
@st.cache_data(ttl=600, show_spinner=False)
def _peaks(servers: tuple):
    d = server_hist(servers, 14)
    return d.groupby("server").cpu_percent.max().to_dict()


@st.cache_data(ttl=900, show_spinner=False)
def _llm_cached(kind: str, facts_json: str, fallback: str):
    import json
    return ex.llm_text(kind, json.loads(facts_json), fallback)


def _set_status(server, status):
    st.session_state.setdefault("opt_status", {})[server] = status


def page_cost():
    import json
    stt = st.session_state.setdefault("opt_status", {})
    t = co.build_table(recs, _peaks(tuple(recs.server)))
    tot = co.totals(t)
    st.markdown(H(f'<div class="banner"><h3>💰 Cost Optimization <span class="tag-sim">{src}</span></h3>'
                  f'<div class="muted">Where are we wasting money, and what can we safely cut? All figures are calculated in Python from the '
                  f'recommendation engine; the AI only explains them. Only CPU is measured: Memory, I/O and Disk are simulated and are '
                  f'<b>not</b> used for any recommendation.</div></div>'), unsafe_allow_html=True)

    c = st.columns(4)
    c[0].markdown(kpi("🏢", money(tot["cost_now"]), "Current Monthly Infrastructure Cost", f"{tot['n']} servers"), unsafe_allow_html=True)
    c[1].markdown(H(f'<div class="card card-save"><div class="kpi"><div class="ic">💚</div><div><div class="val green">{money(tot["gross_saving"])}</div>'
                    f'<div class="lbl">Potential Monthly Savings</div><div class="sub">before {money(tot["extra_for_capacity"])} for capacity additions</div></div></div></div>'),
                  unsafe_allow_html=True)
    c[2].markdown(kpi("📉", money(tot["cost_new"]), "Optimized Projected Monthly Cost", "after all recommendations"), unsafe_allow_html=True)
    c[3].markdown(kpi("🎯", tot["n_candidates"], "Servers Suitable for Optimization", f"{tot['n_review']} need a peak-traffic review"), unsafe_allow_html=True)
    st.write("")

    appr = [s_ for s_, v in stt.items() if v == "Approved"]
    approved_val = float(t[t.server.isin(appr)].saving.sum())
    r1, r2, r3 = st.columns(3)
    r1.markdown(H(f'<div class="card"><div class="muted">Potential savings (identified)</div><div class="big">{money(tot["gross_saving"])}</div></div>'), unsafe_allow_html=True)
    r2.markdown(H(f'<div class="card card-warn"><div class="muted">Approved, not yet applied</div><div class="big orange">{money(approved_val)}</div>'
                  f'<div class="muted">{len(appr)} server(s) approved</div></div>'), unsafe_allow_html=True)
    r3.markdown(H(f'<div class="card"><div class="muted">Realized savings</div><div class="big">{money(0)}</div>'
                  f'<div class="muted">Demo only: no cloud changes are made, so nothing is realized.</div></div>'), unsafe_allow_html=True)
    st.write("")

    # ---- LLM controls ----
    use_llm = st.session_state.get("cost_llm", False)
    b1, b2 = st.columns([1, 3])
    if ex.llm_configured():
        if b1.button("✨ Generate AI explanations", type="primary"):
            st.session_state["cost_llm"] = use_llm = True
        b2.caption("Explanations are written by the configured LLM from the calculated figures; if it fails, a built-in explanation is shown.")
    else:
        b2.info("No LLM configured (set LLM_PROVIDER / LLM_API_KEY, see .env.example). Showing built-in explanations from the same calculated data.")

    sf = co.summary_facts(t, tot)
    fb = co.summary_fallback(sf)
    text, how = _llm_cached("summary", json.dumps(sf), fb) if use_llm else (fb, "fallback")
    label = "AI-generated" if how == "llm" else "built-in summary"
    st.markdown(H(f'<div class="card card-save"><div class="ct">🤖 Overall AI Cost Saving Insights <span class="muted">({label})</span></div>'
                  f'<div style="margin-top:6px">{text}</div></div>'.replace("\n", "<br>")), unsafe_allow_html=True)
    if use_llm and how != "llm":
        st.warning("The LLM was unavailable, so a built-in summary is shown.")
    st.write("")

    # ---- table ----
    st.markdown('<div class="ct">Server-wise cost optimization</div>', unsafe_allow_html=True)
    show_t = pd.DataFrame({
        "Server": [("⭐ " if p else "") + s_ for s_, p in zip(t.server, t.priority)],
        "Current vCPU": t.current_cpus, "Avg CPU %": t.avg_cpu, "Peak CPU %": t.peak_cpu,
        "Current cost / mo": t.cost_now.map(money), "Recommended vCPU": t.recommended_cpus,
        "Optimized cost / mo": t.cost_new.map(money),
        "Potential saving / mo": t.saving.map(money),
        "Status": [stt.get(s_, "Pending") + " · " + l for s_, l in zip(t.server, t.status_label)]})
    color = {"RECOMMENDED": "background-color:rgba(34,197,94,.22)", "REVIEW": "background-color:rgba(245,158,11,.22)",
             "AVOID": "background-color:rgba(239,68,68,.22)", "OPTIMAL": ""}
    sty = show_t.style.apply(lambda r_: [color[t.verdict.iloc[r_.name]]] * len(r_), axis=1)
    st.dataframe(sty, hide_index=True)
    st.caption("⭐ = top three to investigate first. Green = downsize recommended · Orange = review peak traffic first · Red = capacity risk. "
               "Avg CPU is measured over the loaded history; Peak CPU over the last 14 days.")

    # ---- per-server advisor ----
    st.markdown('<div class="ct" style="margin-top:12px">🤖 LLM-powered Cost Saving Advisor</div>', unsafe_allow_html=True)
    vcol = {"RECOMMENDED": GREEN, "REVIEW": AMBER, "AVOID": RED, "OPTIMAL": CYAN}
    for r in t.itertuples():
        f = co.server_facts(r)
        fb = co.server_fallback(r)
        text, how = _llm_cached("server", json.dumps(f), fb) if use_llm else (fb, "fallback")
        col = vcol[r.verdict]
        cur = stt.get(r.server, "Pending")
        d = (f'saves <b class="green">{money(r.saving)}</b>/mo' if r.saving > 0 else
             f'costs <b class="red">{money(-r.saving)}</b> more/mo' if r.saving < 0 else "no change")
        st.markdown(H(f'''<div class="card" style="margin-bottom:6px;border-left:4px solid {col}">
            <span class="ct">{r.server}</span> &nbsp;<span class="badge" style="background:{col}33;color:{col}">{r.status_label}</span>
            <span class="badge" style="background:rgba(59,130,246,.2);color:#93c5fd">{cur}</span>
            <div class="big" style="font-size:1.25rem">{r.current_cpus} → {r.recommended_cpus} vCPUs &nbsp;<span class="muted">{d}</span></div>
            <div class="muted">Avg {r.avg_cpu:.0f}% · observed peak {r.peak_cpu:.0f}% · forecast peak {r.forecast_peak:.0f}% · peak after resize {r.util_after:.0f}%</div>
            <div style="margin-top:8px">{text}</div>
            <div class="muted" style="margin-top:4px">{"AI-generated" if how == "llm" else "built-in explanation"}</div></div>'''), unsafe_allow_html=True)
        if r.verdict != "OPTIMAL":
            a1, a2, a3, _ = st.columns([1.3, 1, 1, 4])
            a1.button("🔍 Review Recommendation", key=f"rv_{r.server}", on_click=_set_status, args=(r.server, "Under review"))
            a2.button("✅ Approve", key=f"ap_{r.server}", type="primary", on_click=_set_status, args=(r.server, "Approved"))
            a3.button("✖ Reject", key=f"rj_{r.server}", on_click=_set_status, args=(r.server, "Rejected"))
            if cur == "Under review":
                st.caption(f"Checklist: confirm peak traffic windows, keep alerts on, apply during the quietest hours. "
                           f"Observed peak would be ≈{r.hist_peak_after:.0f}% at the new size.")
        st.write("")


{"📊 Dashboard": page_dashboard, "💰 Cost Optimization": page_cost, "📈 Forecast": page_forecast,
 "🔔 Alerts": page_alerts, "💡 Recommendations": page_reco}[page]()
