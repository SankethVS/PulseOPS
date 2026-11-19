"""Step 4 - Explain each recommendation in plain English.

Works with Claude, Gemini, OpenAI or a local Ollama model (set env vars, see .env.example).
If no key is set or the call fails, a built-in template is used, so the demo NEVER breaks.
"""
import json
import os
import time
import requests
from config import CURRENCY as CUR

PROVIDER = os.getenv("LLM_PROVIDER", "").lower()   # anthropic | gemini | openai | ollama | (empty = off)
MODEL = os.getenv("LLM_MODEL", "")
API_KEY = os.getenv("LLM_API_KEY", "")

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5-5",
    "gemini": "gemini-3.6-flash",   # gemini-2.0-flash was shut down on 1 Jun 2026
    "openai": "gpt-4o-mini",
    "ollama": "llama3.2",
}


def llm_configured() -> bool:
    if PROVIDER == "ollama":
        return True
    return PROVIDER in DEFAULT_MODELS and bool(API_KEY)


def template_explanation(rec: dict) -> str:
    s, a = rec["server"], rec["action"]
    if a == "DOWNSIZE":
        return (f"{s} has {rec['current_cpus']} vCPUs but is forecast to peak at only "
                f"{rec['forecast_peak_util']}% next week (average {rec['forecast_avg_util']}%). "
                f"Moving to {rec['recommended_cpus']} vCPUs keeps the busiest hour near "
                f"{rec['util_after']}% and saves about {CUR}{rec['monthly_saving']:,.2f} per month. "
                f"Risk: an unusual traffic burst - keep alerts on and review again in a week.")
    if a == "UPSIZE":
        return (f"{s} is forecast to hit {rec['safe_peak_util']}% CPU at its busiest (including a safety "
                f"margin), which risks slowdowns. Adding capacity up to {rec['recommended_cpus']} vCPUs "
                f"brings that near {rec['util_after']}% for about {CUR}{abs(rec['monthly_saving']):,.2f} "
                f"extra per month. Risk: waiting could cause outages during peak hours.")
    return (f"{s} is well sized: forecast peak {rec['forecast_peak_util']}% on {rec['current_cpus']} vCPUs "
            f"leaves healthy headroom without much waste. No change needed; recheck next week.")


def _prompt(rec: dict) -> str:
    facts = {k: rec[k] for k in ("server", "action", "current_cpus", "recommended_cpus",
                                 "forecast_avg_util", "forecast_peak_util", "util_after",
                                 "monthly_saving")}
    return ("You are a cloud cost advisor. Using ONLY these facts, explain the recommendation to a "
            "non-technical manager in 3 short sentences, then add one sentence starting with 'Risk:'. "
            "Do not invent numbers. monthly_saving is in rupees (negative = extra spend).\n"
            f"{json.dumps(facts)}")


def _call_llm(prompt: str) -> str:
    model = MODEL or DEFAULT_MODELS[PROVIDER]
    if PROVIDER == "anthropic":
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=30,
                          headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01",
                                   "content-type": "application/json"},
                          json={"model": model, "max_tokens": 300,
                                "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return r.json()["content"][0]["text"].strip()
    if PROVIDER == "openai":
        r = requests.post("https://api.openai.com/v1/chat/completions", timeout=30,
                          headers={"Authorization": f"Bearer {API_KEY}"},
                          json={"model": model, "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    if PROVIDER == "gemini":
        # Key goes in a header (not the URL) so it can never show up in logs or error messages.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        r = None
        for attempt in range(3):                      # retry on rate-limit / temporary overload
            r = requests.post(url, timeout=30, headers={"x-goog-api-key": API_KEY},
                              json={"contents": [{"parts": [{"text": prompt}]}]})
            if r.status_code not in (429, 500, 503):
                break
            time.sleep(2 ** attempt * 2)              # 2s, 4s, 8s
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if PROVIDER == "ollama":  # offline AI on your own laptop (only if the hackathon allows)
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        r = requests.post(f"{host}/api/generate", timeout=120,
                          json={"model": model, "prompt": prompt, "stream": False})
        r.raise_for_status()
        return r.json()["response"].strip()
    raise ValueError(f"Unknown LLM_PROVIDER: {PROVIDER}")


def explain(rec: dict, use_llm: bool = True) -> tuple[str, str]:
    """Returns (text, source) where source is 'llm' or 'template'."""
    if use_llm and llm_configured():
        try:
            return _call_llm(_prompt(rec)), "llm"
        except Exception as e:
            msg = str(e).replace(API_KEY, "***") if API_KEY else str(e)   # never print the key
            print(f"  (LLM failed for {rec['server']}: {msg}; using template)")
    return template_explanation(rec), "template"
