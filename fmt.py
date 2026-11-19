"""Reusable Indian-currency formatter (Thousand / Lakhs / Crores). Display only: never alters stored numbers."""
from config import CURRENCY


def _num(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def inr(x: float, cur: str = CURRENCY) -> str:
    """45000 -> '₹45 Thousand', 124000 -> '₹1.24 Lakhs', 25000000 -> '₹2.5 Crores'."""
    x = float(x)
    sign, a = ("-" if round(x, 2) < 0 else ""), abs(x)
    if round(a) < 1000:
        return f"{sign}{cur}{round(a):,}"
    for div, one, many in ((1e7, "Crore", "Crores"), (1e5, "Lakh", "Lakhs"), (1e3, "Thousand", "Thousand")):
        if round(a / div, 2) >= (1 if div > 1e3 else 1):
            v = round(a / div, 2)
            if div == 1e3 and v >= 100:          # 99,999.9 -> 1 Lakh, not "100 Thousand"
                continue
            if div == 1e5 and v >= 100:          # 99,99,999 -> 1 Crore
                continue
            return f"{sign}{cur}{_num(v)} {one if v == 1 else many}"
    return f"{sign}{cur}{round(a):,}"


def inr_ticks(vmin: float, vmax: float, n: int = 5):
    """(tickvals, ticktext) so Plotly axes show Indian formatting."""
    if vmax <= vmin:
        vmax = vmin + 1
    step = (vmax - vmin) / (n - 1)
    vals = [vmin + i * step for i in range(n)]
    return vals, [inr(v) for v in vals]
