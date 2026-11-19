"""Central settings. Change numbers here, not scattered around the code."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv():
    """Read KEY=value lines from a .env file next to this file (no extra library needed).
    Real environment variables win over the file."""
    f = BASE_DIR / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()
DATA_DIR = BASE_DIR / "data"
USAGE_CSV = DATA_DIR / "usage.csv"               # simulated demo data
UPLOADED_CSV = Path(os.getenv("UPLOADED_CSV", DATA_DIR / "uploaded.csv"))  # data the user uploads
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "results.db"))

# --- Forecasting ---
HORIZON_HOURS = 168          # forecast the next 7 days (24 * 7)
BACKTEST_HOURS = 168         # hold out the last 7 days to measure accuracy

# --- Cost model (ASSUMPTIONS - state these on your slides) ---
CURRENCY = "₹"
COST_PER_VCPU_HOUR = 3.5     # rupees per vCPU per hour
HOURS_PER_MONTH = 720        # 30 days * 24 hours

# --- Right-sizing rules ---
TARGET_PEAK_UTIL = 70.0      # we want the busiest hour to sit around 70% busy
UPSIZE_ABOVE = 85.0          # forecast peak above this % => server is at risk
DOWNSIZE_TRIGGER = 0.80      # downsize only if we can cut at least 20% of vCPUs
SAFETY_MAE_MULT = 2.0        # add 2 x forecast error to the peak as a safety margin
