"""Step 3 - Turn a forecast into a DECISION (this is what solves the problem statement)."""
import math
import pandas as pd
from config import (COST_PER_VCPU_HOUR, HOURS_PER_MONTH, TARGET_PEAK_UTIL, UPSIZE_ABOVE,
                    DOWNSIZE_TRIGGER, SAFETY_MAE_MULT)


def recommend(server: str, provisioned_cpus: int, history: pd.Series,
              forecast: pd.Series, mae: float) -> dict:
    f_peak = float(forecast.max())
    f_avg = float(forecast.mean())
    # Safety margin: the forecast isn't perfect, so pad the peak by 2x its typical error.
    safe_peak = min(100.0, f_peak + SAFETY_MAE_MULT * mae)

    # vCPUs needed so the (padded) peak lands at the target utilisation.
    needed = max(1, math.ceil(provisioned_cpus * safe_peak / TARGET_PEAK_UTIL))

    if safe_peak > UPSIZE_ABOVE:
        action, recommended = "UPSIZE", max(needed, provisioned_cpus + 1)
    elif needed <= math.floor(provisioned_cpus * DOWNSIZE_TRIGGER):
        action, recommended = "DOWNSIZE", needed
    else:
        action, recommended = "KEEP", provisioned_cpus

    monthly_cost_now = provisioned_cpus * COST_PER_VCPU_HOUR * HOURS_PER_MONTH
    monthly_cost_new = recommended * COST_PER_VCPU_HOUR * HOURS_PER_MONTH
    return {
        "server": server,
        "action": action,
        "current_cpus": int(provisioned_cpus),
        "recommended_cpus": int(recommended),
        "hist_avg_util": round(float(history.mean()), 1),
        "forecast_avg_util": round(f_avg, 1),
        "forecast_peak_util": round(f_peak, 1),
        "safe_peak_util": round(safe_peak, 1),
        "util_after": round(min(100.0, safe_peak * provisioned_cpus / recommended), 1),
        "monthly_cost_now": round(monthly_cost_now, 2),
        "monthly_cost_new": round(monthly_cost_new, 2),
        # positive = money saved, negative = extra spend needed to stay safe
        "monthly_saving": round(monthly_cost_now - monthly_cost_new, 2),
    }
