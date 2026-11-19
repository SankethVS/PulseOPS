"""Cost Optimization logic. No Streamlit here. ALL money is calculated in Python (from recommend.py output);
the LLM only explains these numbers."""
import pandas as pd
from fmt import inr

SAFE_HIST_PEAK = 85.0      # after resizing, the busiest observed hour must stay under this to be 'Recommended'

STATUS = {"RECOMMENDED": "Downsize recommended", "REVIEW": "Review before downsizing",
          "AVOID": "Avoid downsizing (needs capacity)", "OPTIMAL": "Already optimal"}


def build_table(recs: pd.DataFrame, peaks: dict) -> pd.DataFrame:
    t = pd.DataFrame({"server": recs.server, "current_cpus": recs.current_cpus, "avg_cpu": recs.hist_avg_util,
                      "peak_cpu": recs.server.map(peaks).astype(float).round(1),
                      "forecast_peak": recs.forecast_peak_util, "safe_peak": recs.safe_peak_util,
                      "cost_now": recs.monthly_cost_now, "recommended_cpus": recs.recommended_cpus,
                      "cost_new": recs.monthly_cost_new, "saving": recs.monthly_saving, "action": recs.action,
                      "util_after": recs.util_after}).reset_index(drop=True)
    # busiest OBSERVED hour if shrunk to the recommended size (never recommend from the average alone)
    t["hist_peak_after"] = (t.peak_cpu * t.current_cpus / t.recommended_cpus).clip(upper=100).round(1)

    def verdict(r):
        if r.action == "DOWNSIZE":
            return "RECOMMENDED" if r.hist_peak_after <= SAFE_HIST_PEAK else "REVIEW"
        return "AVOID" if r.action == "UPSIZE" else "OPTIMAL"
    t["verdict"] = t.apply(verdict, axis=1)
    t["status_label"] = t.verdict.map(STATUS)
    t["priority"] = False
    top = t[t.verdict.isin(["RECOMMENDED", "REVIEW"])].nlargest(3, "saving").index
    t.loc[top, "priority"] = True
    return t.sort_values("saving", ascending=False).reset_index(drop=True)


def totals(t: pd.DataFrame) -> dict:
    cand = t[t.verdict.isin(["RECOMMENDED", "REVIEW"])]
    gross = float(cand.saving.sum())
    return {"cost_now": float(t.cost_now.sum()), "cost_new": float(t.cost_new.sum()), "gross_saving": gross,
            "extra_for_capacity": float(-t[t.saving < 0].saving.sum()), "n_candidates": len(cand),
            "n_review": int((t.verdict == "REVIEW").sum()), "n_risk": int((t.verdict == "AVOID").sum()),
            "n": len(t)}


def server_facts(r) -> dict:
    return {"server": r.server, "current_vcpus": int(r.current_cpus), "recommended_vcpus": int(r.recommended_cpus),
            "avg_cpu_percent_measured": float(r.avg_cpu), "peak_cpu_percent_measured": float(r.peak_cpu),
            "forecast_peak_percent_next_7_days": float(r.forecast_peak), "forecast_peak_with_safety_margin": float(r.safe_peak),
            "peak_percent_after_resize_forecast": float(r.util_after),
            "observed_peak_percent_after_resize": float(r.hist_peak_after),
            "current_monthly_cost": inr(r.cost_now), "optimized_monthly_cost": inr(r.cost_new),
            "monthly_saving": inr(r.saving) if r.saving >= 0 else "extra " + inr(-r.saving),
            "verdict": STATUS[r.verdict]}


def server_fallback(r) -> str:
    f = server_facts(r)
    base = (f"{r.server} has {f['current_vcpus']} vCPUs; measured average CPU is {r.avg_cpu:.0f}% and its busiest "
            f"observed hour reached {r.peak_cpu:.0f}%. The forecast peak for the next 7 days is {r.forecast_peak:.0f}% "
            f"({r.safe_peak:.0f}% with a safety margin). ")
    if r.verdict in ("RECOMMENDED", "REVIEW"):
        txt = (base + f"Reducing to {f['recommended_vcpus']} vCPUs would cut the monthly cost from {f['current_monthly_cost']} to "
               f"{f['optimized_monthly_cost']}, saving about {f['monthly_saving']}, with the forecast peak near {r.util_after:.0f}%. ")
        txt += ("Risk: if the observed peak repeated at the smaller size it would reach "
                f"{r.hist_peak_after:.0f}%, so check peak traffic first. " if r.verdict == "REVIEW" else
                "Risk: an unusual traffic burst; keep alerts on and recheck in a week. ")
    elif r.verdict == "AVOID":
        txt = (base + f"This server is running hot, so do not downsize it. Adding capacity up to {f['recommended_vcpus']} vCPUs "
               f"would cost about {inr(-r.saving)} more per month. Risk: slowdowns at peak hours if left as is. ")
    else:
        txt = base + "It is well sized with healthy headroom, so no change is needed. "
    return txt + f"Verdict: {f['verdict']}."


def summary_facts(t: pd.DataFrame, tot: dict) -> dict:
    top = t[t.priority].sort_values("saving", ascending=False)
    waste = t[t.saving > 0].nlargest(3, "saving")
    return {"servers_total": tot["n"], "current_monthly_cost": inr(tot["cost_now"]),
            "total_potential_monthly_savings": inr(tot["gross_saving"]),
            "extra_monthly_cost_for_capacity_additions": inr(tot["extra_for_capacity"]),
            "optimized_monthly_cost": inr(tot["cost_new"]), "servers_to_downsize_or_review": tot["n_candidates"],
            "servers_needing_review_for_peak_risk": tot["n_review"], "servers_at_capacity_risk": tot["n_risk"],
            "biggest_waste": [{"server": r.server, "vcpus": f"{int(r.current_cpus)}->{int(r.recommended_cpus)}",
                               "saving": inr(r.saving)} for r in waste.itertuples()],
            "top_three_to_investigate": [{"server": r.server, "saving": inr(r.saving), "verdict": STATUS[r.verdict]}
                                         for r in top.itertuples()],
            "at_risk_servers": t[t.verdict == "AVOID"].server.tolist()}


def summary_fallback(f: dict) -> str:
    top = "; ".join(f"{i + 1}. {x['server']} (saves {x['saving']}, {x['verdict'].lower()})"
                    for i, x in enumerate(f["top_three_to_investigate"])) or "none"
    waste = ", ".join(f"{x['server']} ({x['vcpus']} vCPUs)" for x in f["biggest_waste"]) or "none found"
    risk = (f"Capacity risk: {', '.join(f['at_risk_servers'])} are forecast to run hot and need about "
            f"{f['extra_monthly_cost_for_capacity_additions']} more per month. " if f["at_risk_servers"] else "No servers are at capacity risk. ")
    return (f"Total potential savings are {f['total_potential_monthly_savings']} per month, which would bring the monthly bill from "
            f"{f['current_monthly_cost']} to {f['optimized_monthly_cost']} after any capacity additions. Biggest sources of waste: {waste}. "
            f"Investigate first: {top}. {risk}"
            f"Action plan: 1) review the top servers' peak traffic, 2) approve safe downsizes during the quietest window, "
            f"3) re-check after a week before taking more.")
