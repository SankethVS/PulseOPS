"""One command to run everything:   python start.py
Creates demo data on first run, starts the API (port 8000) and the dashboard (port 8501).
Press Ctrl+C once to stop both."""
import subprocess
import sys
import time

from config import DB_PATH


def main():
    if not DB_PATH.exists():
        print("First run: creating demo data and training models (about a minute)...")
        subprocess.run([sys.executable, "run_pipeline.py", "--regenerate", "--no-llm"], check=True)
    print("Starting API on http://127.0.0.1:8000 ...")
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "api:app", "--port", "8000"])
    time.sleep(3)
    print("Starting dashboard on http://localhost:8501 ...")
    dash = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "dashboard.py", "--server.port", "8501"])
    try:
        dash.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for p in (dash, api):
            p.terminate()


if __name__ == "__main__":
    main()
