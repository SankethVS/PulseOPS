"""pc_monitor.py - reads REAL metrics from the machine this code runs on.

Used by:
  - collector.py  (logs history to a CSV)
  - pc_live.py    (live panel in the Streamlit dashboard)
"""
import os
import time

import psutil

# Disk I/O from psutil is a running total since boot. To get MB/s we remember the
# previous reading and divide the difference by the time that passed.
_last = {"t": None, "read": 0, "write": 0}


def get_metrics() -> dict:
    now = time.time()
    io = psutil.disk_io_counters()  # can be None on some systems
    read_mbps = write_mbps = 0.0
    if io is not None:
        if _last["t"] is not None and now > _last["t"]:
            dt = now - _last["t"]
            read_mbps = max(io.read_bytes - _last["read"], 0) / dt / 1e6
            write_mbps = max(io.write_bytes - _last["write"], 0) / dt / 1e6
        _last.update(t=now, read=io.read_bytes, write=io.write_bytes)

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(os.path.abspath(os.sep))  # C:\ on Windows, / on Linux/Mac

    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_cores": psutil.cpu_count(logical=True),
        "ram_percent": mem.percent,
        "ram_used_gb": round(mem.used / 1e9, 2),
        "ram_total_gb": round(mem.total / 1e9, 2),
        "disk_percent": disk.percent,
        "disk_used_gb": round(disk.used / 1e9, 1),
        "disk_total_gb": round(disk.total / 1e9, 1),
        "disk_read_mbps": round(read_mbps, 2),
        "disk_write_mbps": round(write_mbps, 2),
    }


def get_top_processes(n: int = 5) -> list:
    """Top n processes by memory use (no warm-up needed, unlike CPU per process)."""
    rows = []
    for p in psutil.process_iter(["name", "memory_percent"]):
        try:
            rows.append((p.info["name"] or "?", p.info["memory_percent"] or 0.0))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    rows.sort(key=lambda r: r[1], reverse=True)
    return [{"process": n_, "memory_percent": round(m, 2)} for n_, m in rows[:n]]


if __name__ == "__main__":
    get_metrics()      # prime the counters
    time.sleep(1)
    print(get_metrics())
    print(get_top_processes())
