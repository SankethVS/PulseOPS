# Anveshan: The Clear Picture - Server Capacity Planner
**AI00002 - Paying for Servers Nobody Uses**

Teams over-provision servers "to be safe", then forget them. This prototype **forecasts each server's
usage for the next 7 days with XGBoost** and recommends how many vCPUs it really needs - with the
money saved and a plain-English explanation.

```
usage data -> XGBoost forecast -> right-sizing rules -> LLM explanation
                    |                     |                    |
              Isolation Forest        SQLite  <-->  FastAPI  <-->  Streamlit + Plotly
              (spike detection)
```

## Quick start (5 minutes)
```bash
python -m venv venv
venv\Scripts\activate            # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt

python run_pipeline.py --regenerate     # makes fake data, trains models, fills the database
uvicorn api:app --reload                # Terminal 1 -> http://127.0.0.1:8000/docs
streamlit run dashboard.py              # Terminal 2 -> http://localhost:8501
```
The dashboard also works without the API (it falls back to the database).
Check everything: `python smoke_test.py`

**Easiest: one command** - `python start.py` runs the pipeline (first time only), the API and the dashboard together.

**Check the backend is working:** with the API running, `python check_backend.py` tests every endpoint.
In the dashboard sidebar a green dot means *Backend connected*; amber means it is reading saved results only.

Or with Docker: `docker compose up --build` -> dashboard at http://localhost:8501

## Files and who owns them
| File | What it does | Owner |
|---|---|---|
| `generate_data.py`, `forecast.py`, `anomaly.py`, `recommend.py` | fake data, XGBoost forecast, Isolation Forest, right-sizing rules | Member 1 |
| `explain.py` | LLM explanations (Claude/Gemini/OpenAI/Ollama) + offline fallback | Member 2 |
| `dashboard.py`, `dash_logic.py`, `.streamlit/config.toml` | dark AIOps dashboard (4 pages) and its data logic (and the PPT) | Member 3 |
| `dashboard_classic.py` | simpler light-style dashboard, kept as a backup (`streamlit run dashboard_classic.py`) | Member 3 |
| `api.py`, `db.py`, `data_access.py`, `Dockerfile`, `docker-compose.yml` | FastAPI, SQLite, Docker, Git | Member 4 |
| `run_pipeline.py`, `config.py` | glue and settings | everyone |

## Turn on the LLM explanations (optional)
1. Copy `.env.example` to a new file named `.env` (same folder as `run_pipeline.py`).
2. Open `.env` and fill in two lines, no spaces or quotes needed:
   ```
   LLM_PROVIDER=anthropic
   LLM_API_KEY=your-key-here
   ```
   (`LLM_PROVIDER` can be `anthropic`, `gemini`, `openai` or `ollama`. Optional: `LLM_MODEL=` to pick a model.)
3. Restart the API and dashboard, then press **Re-run on demo data** (or run `python run_pipeline.py`).
   Cards switch from "(template explanation)" to real LLM text.

`.env` is already in `.gitignore`. **Never commit or share your key.** Without a key the built-in explanations are used, so the demo never breaks.

## How the pieces connect
```
Dashboard (Streamlit :8501)  --HTTP-->  FastAPI (:8000)  -->  SQLite (results.db)
   sidebar upload ----------> POST /upload ---> ingest.py validates -> run_pipeline.py -> forecast + decisions
   charts <------------------ GET /fleet, /recommendations, /forecast/{server} ...
```
If the API is not running, the dashboard reads SQLite directly so a demo never dies.

## Analyse real data from the dashboard
Sidebar -> **Analyse your own data** -> upload a CSV -> **Analyse my data**. The top bar then says
"Your uploaded data". Use **Download sample CSV** to see the exact format. **Re-run on demo data** switches back.

## Use real data (command line)
Provide a CSV named `data/usage.csv` (or `--csv path`) with hourly rows and these columns:
`timestamp, server, cpu_percent, provisioned_cpus` - at least 16 days per server (30+ recommended).

## How the AI works (for judges)
1. **Features**: hour, weekday, weekend flag, usage 24h ago, usage 7 days ago, 24h and 7-day averages.
2. **Forecast**: XGBoost predicts hour by hour for 7 days (each prediction feeds the next).
3. **Honest accuracy**: the last 7 days are hidden, forecast, then compared with reality (MAE), and
   compared with a simple "repeat last week" baseline.
4. **Safety margin**: forecast peak + 2 x MAE, so decisions allow for forecast error.
5. **Decision**: size so the busiest hour is ~70% busy. Above 85% => UPSIZE. Needs at least 20% fewer vCPUs => DOWNSIZE.

## Demo script (3 minutes)
1. Problem: "servers sized for the worst case, usage data never used".
2. Dashboard KPIs: "we found ₹X/month of waste."
3. Fleet chart: batch-01 pays for 32 vCPUs but needs ~11.
4. Server detail: forecast, spikes, explanation. Show **app-02 (UPSIZE)** - the tool also prevents outages.
5. Accuracy tab: AI beats the baseline.
6. Click **Re-run analysis** with new data to show it is live.

## Honest limitations (say these - judges respect it)
- Data is simulated; the cost (₹3.5/vCPU-hour) is an assumption.
- CPU only; memory, disk and network are the next step.
- Tree models cannot extrapolate beyond what they have seen, so a sudden step-change in demand needs retraining.
- Forecasts use recent history only; planned events (sales, launches) are not known to the model.
