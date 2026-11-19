"""Tests every API endpoint and tells you what is wrong.   python check_backend.py
(Start the API first:  uvicorn api:app)"""
import os
import sys

import requests

API = os.getenv("API_URL", "http://127.0.0.1:8000")


def get(path):
    r = requests.get(API + path, timeout=10)
    r.raise_for_status()
    return r.json()


def check(name, fn):
    try:
        info = fn()
        print(f"  PASS  {name}" + (f"  ({info})" if info else ""))
        return True
    except requests.exceptions.ConnectionError:
        print(f"  FAIL  {name}: cannot reach {API}. Is `uvicorn api:app` running in another terminal?")
        sys.exit(1)
    except Exception as e:
        print(f"  FAIL  {name}: {e}")
        return False


print(f"Checking backend at {API}\n")
results = [check("/health", lambda: get("/health")["status"])]
recs = []
results.append(check("/recommendations", lambda: recs.extend(get("/recommendations")) or f"{len(recs)} servers"))
if recs:
    s = recs[0]["server"]
    results += [
        check("/summary", lambda: f"saves {get('/summary')['monthly_savings']}/month"),
        check("/fleet", lambda: f"{len(get('/fleet')['forecast'])} forecast rows"),
        check(f"/history/{s}", lambda: f"{len(get(f'/history/{s}'))} rows"),
        check(f"/forecast/{s}", lambda: f"{len(get(f'/forecast/{s}'))} rows"),
        check(f"/backtest/{s}", lambda: f"{len(get(f'/backtest/{s}'))} rows"),
        check(f"/anomalies/{s}", lambda: f"{len(get(f'/anomalies/{s}'))} rows"),
    ]
else:
    print("  No results yet. Run: python run_pipeline.py --regenerate")
print("\nALL GOOD - dashboard will show 'Backend connected'." if all(results) else "\nSome checks failed.")
