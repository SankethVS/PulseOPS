"""FastAPI backend.  Run:  uvicorn api:app --reload      Test page: http://127.0.0.1:8000/docs"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from starlette.concurrency import run_in_threadpool

import data_access as da
import ingest
import run_pipeline

app = FastAPI(title="Anveshan: The Clear Picture - Capacity Planner API",
              description="Forecasts server usage with XGBoost and recommends right-sizing.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _servers():
    return [r["server"] for r in da.get_recommendations()]


def _check(server: str):
    if server not in _servers():
        raise HTTPException(404, f"Unknown server '{server}'. Run the pipeline first?")


@app.get("/health")
def health():
    return {"status": "ok", "servers_analysed": len(_servers())}


@app.get("/summary")
def summary():
    recs = da.get_recommendations()
    return {
        "servers": len(recs),
        "to_downsize": sum(r["action"] == "DOWNSIZE" for r in recs),
        "to_upsize": sum(r["action"] == "UPSIZE" for r in recs),
        "monthly_savings": round(sum(r["monthly_saving"] for r in recs if r["monthly_saving"] > 0), 2),
        "extra_spend_for_safety": round(-sum(r["monthly_saving"] for r in recs if r["monthly_saving"] < 0), 2),
    }


@app.get("/fleet")
def fleet():
    return da.get_fleet()


@app.get("/recommendations")
def recommendations():
    return da.get_recommendations()


@app.get("/history/{server}")
def history(server: str, days: int = 14):
    _check(server)
    return da.get_history(server, days)


@app.get("/forecast/{server}")
def forecast(server: str):
    _check(server)
    return da.get_forecast(server)


@app.get("/backtest/{server}")
def backtest(server: str):
    _check(server)
    return da.get_backtest(server)


@app.get("/anomalies/{server}")
def anomalies(server: str):
    _check(server)
    return da.get_anomalies(server)


@app.post("/upload")
async def upload(request: Request, use_llm: bool = True):
    """Send a CSV as the raw request body (Content-Type: text/csv). Validates it, then analyses it."""
    raw = await request.body()
    try:
        n = await run_in_threadpool(ingest.process_upload, raw, use_llm)
    except ValueError as e:                       # friendly validation message -> HTTP 400
        raise HTTPException(400, str(e))
    return {"status": "done", "servers": n}


@app.post("/run-pipeline")
def run_now(regenerate: bool = False, use_llm: bool = True):
    """Re-run the whole analysis (optionally with brand-new fake data)."""
    recs = run_pipeline.run(use_llm=use_llm, regenerate=regenerate, verbose=False)
    return {"status": "done", "servers": len(recs)}
