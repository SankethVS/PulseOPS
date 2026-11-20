<div align="center">

# ⚡ OptiScale AI

### *Anveshan: The Clear Picture*
**Stop paying for servers nobody uses.**

<br>

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost-Forecasting-EC6B23?style=for-the-badge)
![scikit-learn](https://img.shields.io/badge/scikit--learn-Isolation_Forest-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-Charts-3F4F75?style=for-the-badge&logo=plotly&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)

<br>

**🔮 Forecast &nbsp;•&nbsp; 📏 Right-size &nbsp;•&nbsp; 💰 Save money &nbsp;•&nbsp; 🗣️ Explained in plain English**

<br>

[🚀 Quick Start](#-quick-start) · [🧠 How It Works](#-how-it-works) · [📁 Files](#-every-file-explained) · [✨ Features](#-features) · [📊 Use Your Data](#-use-your-own-data) · [💻 This PC (live)](#-this-pc-live) · [🌐 Share a Demo](#-share-a-temporary-public-demo) · [🎬 Demo](#-3-minute-demo-script)

</div>

---

## 🎯 The Problem

> **AI00002 — Paying for Servers Nobody Uses**

Teams give their servers **more CPU than they need "just to be safe"**, then forget about them. Every unused vCPU is money burned, every single hour.

Meanwhile, the usage data that could fix this just sits there, never used.

## 💡 The Solution

OptiScale AI reads each server's past CPU usage and does four things:

| Step | What happens | Tool |
|:---:|---|---|
| 1️⃣ | **Predicts** the next 7 days of usage, hour by hour | XGBoost |
| 2️⃣ | **Spots** unusual spikes | Isolation Forest |
| 3️⃣ | **Recommends** how many vCPUs each server really needs, and how much money that saves | Right-sizing rules |
| 4️⃣ | **Explains** every recommendation in plain English | An LLM (or an offline fallback) |

It works in **both directions**. It tells you when a server is too big (**DOWNSIZE**), and also when one is about to run out of room (**UPSIZE**), so it helps prevent outages too.

> 🧭 **Who does what:** the **ML model forecasts**, **plain rules decide**, and the **LLM only explains**. The LLM never touches the numbers, so every decision is repeatable and cannot be hallucinated.

---

## 🧠 How It Works

```mermaid
flowchart LR
    A[📄 Usage data<br/>CPU % per hour] --> B[🔮 XGBoost<br/>7-day forecast]
    A --> C[🚨 Isolation Forest<br/>spike detection]
    B --> D[📏 Right-sizing<br/>rules]
    D --> E[🗣️ LLM<br/>explanation]
    D --> F[(🗄️ SQLite<br/>results.db)]
    C --> F
    E --> F
    F <--> G[⚙️ FastAPI<br/>:8000]
    G <--> H[📊 Streamlit + Plotly<br/>dashboard :8501]
    P[💻 This PC<br/>live readings] --> H
    P -. collector.py logs hourly .-> A
```

### The pieces talk like this

```
Dashboard (Streamlit :8501)  ──HTTP──▶  FastAPI (:8000)  ──▶  SQLite (results.db)

  sidebar upload ───────▶ POST /upload ──▶ ingest.py validates ──▶ run_pipeline.py ──▶ forecast + decisions
  charts ◀──────────────  GET /fleet, /recommendations, /forecast/{server} ...
```

> 🛟 **Safety net:** if the API isn't running, the dashboard reads the SQLite database directly, so a demo never dies.

### What happens when you run it with no upload

```
generate_data.py  ->  fake hourly usage (60 days, 5 servers)
        |
        v
for each server:  train XGBoost  ->  detect spikes  ->  apply sizing rules  ->  explain
        |
        v
SQLite (results.db)  ->  dashboard
```

The default demo trains on **simulated data**. The pipeline is identical for real data: upload a CSV and the same steps run on it. **Each server gets its own model, trained from its own history**, in seconds, on a normal laptop. Nothing is pre-trained and nothing carries over between uploads.

---

## 🚀 Quick Start

### Option 1: ⚡ The easy way (recommended)

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate              # Windows
# source venv/bin/activate         # Mac / Linux

# 2. Install the libraries
pip install -r requirements.txt

# 3. Run everything with one command
python start.py
```

`start.py` runs the pipeline (first time only), the API and the dashboard together. Then open **http://localhost:8501** 🎉

### Option 2: 🔧 Step by step

```bash
python run_pipeline.py --regenerate     # makes fake data, trains models, fills the database
uvicorn api:app --reload                # Terminal 1 → http://127.0.0.1:8000/docs
streamlit run dashboard.py              # Terminal 2 → http://localhost:8501
```

### Option 3: 🐳 Docker

```bash
docker compose up --build
```
Dashboard at **http://localhost:8501**

### ✅ Check that everything works

| Command | What it checks |
|---|---|
| `python smoke_test.py` | The whole project, end to end |
| `python check_backend.py` | Every API endpoint (API must be running) |

In the dashboard sidebar:
🟢 **Green dot** = Backend connected &nbsp;|&nbsp; 🟠 **Amber dot** = reading saved results only

---

## ✨ Features

| | Feature | What it means |
|:---:|---|---|
| 🔮 | **7-day forecast per server** | XGBoost predicts CPU usage hour by hour, and each prediction feeds the next |
| 📏 | **Smart right-sizing** | Recommends the exact vCPU count, not a guess |
| 🛡️ | **Safety margin** | Decisions allow for forecast error, so you don't cut too deep |
| 🎯 | **Honest accuracy test** | Hides the last 7 days, forecasts them, then compares with reality |
| 🚨 | **Spike detection** | Isolation Forest flags abnormal usage |
| 💰 | **Money saved** | Shows ₹ waste found per month |
| 🗣️ | **Plain-English explanations** | Powered by Claude / Gemini / OpenAI / Ollama, with an offline fallback |
| 📤 | **Upload your own CSV** | Analyse real data right from the sidebar |
| 💻 | **This PC (live)** | Real readings from the computer running the dashboard, refreshed every 2 seconds, plus a collector that builds history for the AI forecast |
| 🌗 | **Two dashboards** | A dark AIOps dashboard (4 pages) and a simpler classic one |
| 🔌 | **REST API** | Interactive docs at `/docs` |
| 🐳 | **Docker support** | One command to run it all |
| 🌐 | **Temporary public link** | Share the demo with a Cloudflare quick tunnel |
| 🧯 | **Never breaks in a demo** | Falls back to the database and to template explanations |

---

## 🤖 How the AI Works

> *A short tour in 5 steps, written for beginners and judges alike.*

### 1️⃣ Features: what the model looks at
For every hour, the model learns from:
- 🕐 hour of the day
- 📅 day of the week
- 🏖️ weekend or not
- ⏪ usage **24 hours ago**
- ⏮️ usage **7 days ago**
- 📈 the **24-hour** and **7-day averages**

The answer it learns to predict is simply the CPU % that was recorded at that hour, so no manual labelling is needed. This is why the same code works on fake data and on real CSVs.

### 2️⃣ Forecast
XGBoost predicts the next **7 days, hour by hour**. Each predicted hour is fed back in to predict the next one.

### 3️⃣ Honest accuracy
We hide the **last 7 days**, forecast them, then compare with what really happened (error measured as **MAE**). We also compare against a simple baseline, *"just repeat last week"*, to prove the AI is actually better.

### 4️⃣ Safety margin
```
safe peak = forecast peak + 2 × MAE
```
Forecasts are never perfect, so we add room for error.

### 5️⃣ Decision

| Situation | Decision |
|---|---|
| Busiest hour would be **above 85%** busy | 🔴 **UPSIZE** |
| Needs **at least 20% fewer** vCPUs | 🟢 **DOWNSIZE** |
| Anything else | ⚪ **KEEP** |

New size is chosen so the **busiest hour is about 70% busy**.

### 🧮 A worked example *(illustrative numbers)*

A server has **32 vCPUs**. The safe forecast peak needs about **7.7 vCPUs** of real work.

```
needed size = 7.7 ÷ 0.70 ≈ 11 vCPUs
```
That's well over 20% fewer than 32, so the decision is **DOWNSIZE: 32 → 11 vCPUs**.

At the assumed cost of ₹3.5 per vCPU-hour:
```
21 vCPUs saved × ₹3.5 × 24 hours × 30 days ≈ ₹52,920 / month
```

### 🧪 The simulated demo fleet

The demo data imitates the four things real servers do: a **daily rhythm** (busiest around noon), a **weekly rhythm** (weekends about 40% quieter), **slow growth**, and **random spikes**. Five servers are generated for 60 days (fixed seed, so every run is identical):

| Server | Provisioned | Story |
|---|:---:|---|
| `web-01` | 16 vCPUs | way over-provisioned |
| `db-01` | 16 vCPUs | somewhat over-provisioned |
| `api-01` | 8 vCPUs | about right |
| `batch-01` | 32 vCPUs | hugely over-provisioned |
| `app-02` | 4 vCPUs | **under-provisioned and growing** → UPSIZE |

> ⚠️ These outcomes are built into the simulator. The demo shows that the pipeline works end to end, not that the savings figure is a real-world measurement. Use your own data (below) for that.

---

## 📁 Every File Explained

### 🗂️ Project map

```
PulseOPS/
├── 🧠 AI & data
│   ├── generate_data.py      → fake demo data
│   ├── ingest.py             → validates uploaded CSVs
│   ├── forecast.py           → XGBoost 7-day forecast
│   ├── anomaly.py            → Isolation Forest spikes
│   ├── recommend.py          → UPSIZE / DOWNSIZE / KEEP + savings
│   ├── cost_opt.py           → cost tables and totals behind the savings figures
│   └── explain.py            → LLM explanations + offline fallback
│
├── ⚙️ Backend
│   ├── api.py                → FastAPI server
│   ├── db.py                 → SQLite setup
│   └── data_access.py        → helpers to read results
│
├── 📊 Frontend
│   ├── dashboard.py          → main dark dashboard (4 pages)
│   ├── dash_logic.py         → data logic behind the dashboard
│   ├── dashboard_classic.py  → simple light backup dashboard
│   ├── pc_live.py            → "This PC (live)" panel
│   ├── fmt.py                → ₹ and number formatting helpers
│   └── .streamlit/           → dashboard theme settings
│
├── 💻 Live PC monitoring
│   ├── pc_monitor.py         → reads this computer's CPU, RAM, disk and processes
│   └── collector.py          → logs hourly readings so the AI can forecast this PC
│
├── 🔗 Glue & tools
│   ├── run_pipeline.py       → runs the whole chain
│   ├── start.py              → one-command launcher
│   ├── config.py             → settings (e.g. cost per vCPU-hour)
│   ├── check_backend.py      → tests API endpoints
│   └── smoke_test.py         → tests the whole project
│
└── 📦 Setup
    ├── requirements.txt      → Python libraries
    ├── Dockerfile            → builds the app image
    ├── docker-compose.yml    → runs everything in Docker
    ├── .env.example          → template for your LLM key
    ├── .gitignore            → files Git should skip
    ├── .vscode/              → editor settings
    └── welcome.txt           → welcome message
```

### 🧠 AI & data

| File | What it does |
|---|---|
| **`generate_data.py`** | Creates realistic **fake hourly CPU data** for 5 demo servers, so the project works with zero setup |
| **`ingest.py`** | The **gatekeeper**. Cleans and checks an uploaded CSV (columns, data types, value ranges, enough history) before anything runs |
| **`forecast.py`** | Trains **XGBoost** (one model per server) and predicts the next 7 days. Also measures its own accuracy |
| **`anomaly.py`** | Uses **Isolation Forest** to flag unusual usage spikes |
| **`recommend.py`** | The **decision maker**. Applies the sizing rules and calculates the savings |
| **`cost_opt.py`** | Builds the **cost tables and totals** shown on the dashboard |
| **`explain.py`** | Asks an **LLM** to explain each decision. Without an API key, it uses built-in template text |

### ⚙️ Backend

| File | What it does |
|---|---|
| **`api.py`** | The **FastAPI** server. The dashboard asks it for data over HTTP |
| **`db.py`** | Creates and manages the **SQLite** database (`results.db`) |
| **`data_access.py`** | Small helper functions that **read results** from the database |

### 📊 Frontend

| File | What it does |
|---|---|
| **`dashboard.py`** | The main **dark AIOps dashboard** (4 pages) built with Streamlit and Plotly |
| **`dash_logic.py`** | The **logic behind the dashboard**: preparing data and numbers for the charts |
| **`dashboard_classic.py`** | A simpler **light-style backup**. Run it with `streamlit run dashboard_classic.py` |
| **`pc_live.py`** | The **"This PC (live)"** panel: live CPU, RAM, disk and top processes, plus collected-history progress |
| **`fmt.py`** | Formatting helpers, such as showing money in ₹ |
| **`.streamlit/config.toml`** | Dashboard **theme and appearance** |

### 💻 Live PC monitoring

| File | What it does |
|---|---|
| **`pc_monitor.py`** | Reads the **current metrics** of the computer running the dashboard |
| **`collector.py`** | Runs in a terminal and **logs readings to `data/mypc_raw.csv`**. With `--export` it writes `data/usage_mypc.csv` in the pipeline's CSV format |

### 🔗 Glue & tools

| File | What it does |
|---|---|
| **`run_pipeline.py`** | The **conductor**: data → forecast → decisions → explanations → database |
| **`start.py`** | **One command** to launch pipeline, API and dashboard together |
| **`config.py`** | Central **settings**, like the assumed ₹3.5 per vCPU-hour |
| **`check_backend.py`** | Tests **every API endpoint** while the API is running |
| **`smoke_test.py`** | A quick **health check** of the whole project |

### 📦 Setup files

| File | What it does |
|---|---|
| **`requirements.txt`** | List of Python libraries for `pip install` |
| **`Dockerfile`** / **`docker-compose.yml`** | Run the project inside Docker |
| **`.env.example`** | Template for your **private** LLM settings |
| **`.gitignore`** | Keeps secrets like `.env` out of Git |

---

## 🔌 API Endpoints

Start the API, then open **http://127.0.0.1:8000/docs** for an interactive page where you can try everything.

| Method | Endpoint | Returns |
|:---:|---|---|
| `GET` | `/fleet` | Overview of all servers |
| `GET` | `/recommendations` | UPSIZE / DOWNSIZE / KEEP for each server |
| `GET` | `/forecast/{server}` | The 7-day forecast for one server |
| `GET` | `/history/{server}` | Past usage for one server |
| `POST` | `/upload` | Upload a CSV, then validate, analyse and save it |

> The `/docs` page lists every endpoint, including ones not shown here.

---

## 📊 Use Your Own Data

Uploading **retrains the models from scratch on your data**. Nothing is pre-trained, and your data stays on your machine. Only the optional LLM explanation step calls an outside service.

### From the dashboard 🖱️
1. Open the **sidebar** → **Analyse your own data**
2. Upload your CSV
3. Click **Analyse my data**
4. The top bar now says *"Your uploaded data"* ✅

💡 Click **Download sample CSV** to see the exact format. Click **Re-run on demo data** to switch back (this replaces the uploaded results with the simulated ones).

### From the command line ⌨️
```bash
python run_pipeline.py --csv path/to/your.csv
```
Add `--no-llm` to skip the LLM and use the built-in explanations.

### 📋 CSV format

Hourly rows with these columns:

| timestamp | server | cpu_percent | provisioned_cpus |
|---|---|---|---|
| 2026-01-01 00:00 | web-01 | 23.4 | 8 |
| 2026-01-01 01:00 | web-01 | 19.8 | 8 |

### ✅ What gets checked

| Rule | What happens |
|---|---|
| Empty or unreadable file | Rejected with a plain-English message |
| Missing columns | Rejected, and the message lists the missing ones |
| Unreadable dates or numbers | Those rows are **dropped** (a count is printed in the terminal) |
| `cpu_percent` outside 0–100 | **Clipped** into range |
| `provisioned_cpus` zero or negative | Rejected |
| More than **30 servers** | Rejected (prototype limit) |
| Fewer than **384 hourly readings** per server (16 days) | Rejected, naming the servers that are too short |
| Gaps in the hourly series | Small gaps are **filled by interpolation** |

> ⚠️ You need **at least 16 days per server** (30+ days is better). Readings finer than hourly, like every 5 minutes, are averaged into hours. Use **one consistent `provisioned_cpus` per server**: the pipeline uses the last value, so a mid-history resize would distort the result.

---

## 💻 This PC (live)

Pick **💻 This PC (live)** in the server dropdown to see **real readings from the computer running the dashboard**: CPU, RAM, disk usage, disk I/O and the top processes by memory. The panel refreshes every 2 seconds (needs Streamlit 1.37 or newer; on older versions a Refresh button is shown).

### Is it forecast too?

Not instantly. The live view shows the present moment, while the forecast model works on **hourly history** and needs **16 days** of it. To get the AI forecast for your own PC:

```bash
# 1. In a separate terminal, leave this running (it logs readings to data/mypc_raw.csv)
python collector.py

# 2. After about 16 days (384 hourly readings), export it in the pipeline's format
python collector.py --export        # writes data/usage_mypc.csv

# 3. In the dashboard sidebar → Analyse your own data → upload data/usage_mypc.csv
```

The page shows a **progress bar** of how many hourly readings have been collected so far.

> ℹ️ **Scope:** the live panel shows RAM and disk too, but the **forecast and sizing decisions use CPU only**. Your PC is not billed like a cloud server, so treat the result as *"what size cloud VM would this workload need"*.
>
> 🔒 **Privacy:** the panel shows the machine running the app. If you share the dashboard over a public link, everyone with the link can see this PC's stats. Don't expose it during a public demo unless you mean to.

---

## 🌐 Share a Temporary Public Demo

Want a judge or teammate to open your dashboard from their own device? A **Cloudflare quick tunnel** gives your local app a temporary public link. No account or deployment is needed.

```bash
# 1. Start the app
python start.py

# 2. Install cloudflared (one time)
winget install Cloudflare.cloudflared        # Windows
brew install cloudflared                     # Mac

# 3. In a second terminal, open the tunnel to the dashboard port
cloudflared tunnel --url http://localhost:8501
```

It prints a link like `https://random-words.trycloudflare.com`. Share it.

- ⏳ The link works **only while the app and `cloudflared` are both running**, and you get a new link each time.
- 🟠 Only the dashboard is exposed, so the sidebar shows the **amber dot** (reading saved results). That's fine, the dashboard falls back to the database.
- ⚠️ **Anyone with the link can use the app**, including the CSV upload and re-run buttons. There is no login. Leave the LLM key out of `.env` for public demos so visitors can't spend your credits.
- 💻 Hide or avoid the **This PC (live)** view while the tunnel is open.
- If Streamlit shows a websocket error through the tunnel, restart it with `streamlit run dashboard.py --server.enableCORS false --server.enableXsrfProtection false`.

---

## 🗣️ Turn On the LLM Explanations *(optional)*

Without a key, you get template explanations. With one, you get real AI-written ones. The LLM only **explains** a decision that has already been made by the rules, so turning it on or off never changes the recommendations.

**1.** Copy `.env.example` to a new file named `.env` (same folder as `run_pipeline.py`).

**2.** Fill in two lines (no spaces or quotes needed):

```env
LLM_PROVIDER=anthropic
LLM_API_KEY=your-key-here
```

| `LLM_PROVIDER` | Service |
|---|---|
| `anthropic` | Claude |
| `gemini` | Google Gemini |
| `openai` | OpenAI |
| `ollama` | Local models, no key needed |

You can also set `LLM_MODEL=` to pick a specific model.

**3.** Restart the API and dashboard, then click **Re-run on demo data** (or run `python run_pipeline.py`). Cards change from *"(template explanation)"* to real LLM text. ✨

> 🔒 **Never commit or share your key.** `.env` is already in `.gitignore`.

---

## 🩺 Troubleshooting

| Problem | Try this |
|---|---|
| Dashboard shows an **amber dot** | The API isn't running. Start it with `uvicorn api:app --reload`, or just use `python start.py` |
| Explanations say **"(template explanation)"** | No LLM key is set. See the LLM section above |
| `ModuleNotFoundError` / import errors | Activate your virtual environment (`venv\Scripts\activate`), then run `pip install -r requirements.txt` again |
| Empty dashboard | Run `python run_pipeline.py --regenerate` to rebuild the data and database |
| Upload says **"Not enough history"** | Each server needs at least 384 distinct hourly readings (16 days) |
| Upload says **"Missing column(s)"** | Check the header row: `timestamp, server, cpu_percent, provisioned_cpus` |
| This PC (live) says **"No history yet"** | Run `python collector.py` in a terminal and leave it running |
| This PC (live) doesn't refresh | Upgrade Streamlit: `pip install -U streamlit` |
| Not sure what's broken | Run `python smoke_test.py` and `python check_backend.py` |

---

## 🎬 3-Minute Demo Script

1. 🎤 **Problem:** *"Servers are sized for the worst case, and usage data is never used."*
2. 💰 **KPIs:** *"We found ₹X per month of waste."*
3. 📊 **Fleet chart:** `batch-01` pays for 32 vCPUs but needs about 11. Point at the gap between the fleet average (about 20–30%) and the busiest server.
4. 🔍 **Server detail:** show the forecast, spikes and explanation. Show **app-02 (UPSIZE)** to prove the tool also **prevents outages**.
5. 🎯 **Accuracy tab:** the AI beats the "repeat last week" baseline.
6. 💻 **This PC (live):** *"These are real readings from this laptop. The same pipeline runs on real data once enough history is collected."*
7. 🔄 **Re-run analysis** with new data to show it is live.

> 🗣️ **If asked "who makes the recommendation?"** The ML model forecasts, deterministic rules decide, and the LLM only explains.

---

## ⚠️ Honest Limitations

*We say these out loud. Judges respect honesty.*

**Data**
- 🧪 The **demo fleet is simulated** and its outcomes are built into the generator. Uploaded CSVs and the live PC panel use real data, but the savings headline is only as real as the input.
- 💵 The **₹3.5 per vCPU-hour** cost is an assumption. Real clouds have fixed instance sizes, reserved pricing and discounts.
- ⏳ Each server needs **16+ days** of hourly history. New servers, or ones just resized, can't be analysed yet.

**Forecast**
- 🖥️ **Forecast and decisions are CPU only.** A server with low CPU can still be limited by memory, disk or network, so shrinking on CPU alone could cause trouble. The live PC panel shows RAM and disk, but they don't feed the forecast yet.
- 📈 Tree models **can't extrapolate** beyond what they've seen, so a sudden step-change in demand needs retraining.
- 📅 Forecasts use **recent history only**. Planned events (sales, launches) are unknown to the model.
- 🔁 Each predicted hour feeds the next, so errors can **accumulate** toward the end of the 7 days.

**Decisions**
- 📏 The **70% / 85% / 20% thresholds are rules of thumb**, not tuned per workload. A latency-sensitive service may need more headroom than a batch job.
- 🧑‍⚖️ The tool **recommends, it doesn't act.** A human should approve every change.
- 🚨 Isolation Forest flags unusual points but can't tell a harmless spike from a real incident.

**System**
- 🔓 No login: anyone who can reach the app can upload data or re-run the analysis.
- 🗄️ SQLite is fine for a prototype but won't scale to a large fleet or many users. Uploads are capped at 30 servers.

## 🔭 What's Next

- [ ] Add memory, disk and network metrics to the **forecast** (the live panel already shows them)
- [ ] Run the forecast on the collected PC history automatically once 16 days exist
- [ ] Feed in planned events (sales, launches)
- [ ] Automatic retraining when demand shifts
- [ ] Connect to real monitoring sources
- [ ] Validate on real production or public cluster traces
- [ ] Add login and a proper database

---

## 👥 Team & Ownership

| File(s) | Role | Owner |
|---|---|---|
| `generate_data.py`, `forecast.py`, `anomaly.py`, `recommend.py` | 🧠 Data, forecasting, spike detection, sizing rules | **Member 1** |
| `explain.py` | 🗣️ LLM explanations + offline fallback | **Member 2** |
| `dashboard.py`, `dash_logic.py`, `dashboard_classic.py`, `pc_live.py`, `.streamlit/` | 🎨 Dashboard and presentation | **Member 3** |
| `api.py`, `db.py`, `data_access.py`, `Dockerfile`, `docker-compose.yml` | ⚙️ API, database, Docker, Git | **Member 4** |
| `run_pipeline.py`, `ingest.py`, `config.py` | 🔗 Glue and settings | **Everyone** |

---

<div align="center">

### ⚡ Built for the AI Ops Hackathon

*Because every idle vCPU is money you'll never get back.*

⭐ **Star this repo if it helped you!** ⭐

</div>
