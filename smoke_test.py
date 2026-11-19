"""Quick self-check: python smoke_test.py"""
import os, tempfile
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

import run_pipeline, data_access as da

recs = run_pipeline.run(csv_path=os.path.join(tempfile.mkdtemp(), "u.csv"),
                        use_llm=False, regenerate=True, verbose=False)
assert len(recs) == 5, "expected 5 servers"
assert {r["action"] for r in recs} <= {"DOWNSIZE", "KEEP", "UPSIZE"}
assert all(r["forecast_mae"] < r["baseline_mae"] * 1.2 for r in recs), "model much worse than baseline"
assert len(da.get_forecast("web-01")) == 168
assert len(da.get_backtest("web-01")) == 168
assert da.get_recommendations()[0]["explanation"]
print("ALL CHECKS PASSED")
