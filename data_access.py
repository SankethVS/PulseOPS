"""Read results from SQLite. Used by the API, and by the dashboard as a fallback if the API is down."""
from db import query


def get_fleet(hist_hours: int = 48):
    """Everything the main dashboard needs, in one call."""
    return {
        "history": query("SELECT server, timestamp, cpu_percent FROM usage WHERE timestamp >= "
                         "(SELECT datetime(MAX(timestamp), ?) FROM usage)", (f"-{hist_hours} hours",)),
        "forecast": query("SELECT server, timestamp, forecast_cpu FROM forecasts ORDER BY timestamp"),
        "anomalies": query("SELECT server, timestamp, cpu_percent, deviation FROM anomalies ORDER BY timestamp"),
    }


def get_recommendations():
    return query("SELECT * FROM recommendations ORDER BY monthly_saving DESC")


def get_history(server: str, days: int = 14):
    return query("SELECT timestamp, cpu_percent FROM usage WHERE server = ? "
                 "ORDER BY timestamp DESC LIMIT ?", (server, days * 24))[::-1]


def get_forecast(server: str):
    return query("SELECT timestamp, forecast_cpu FROM forecasts WHERE server = ? ORDER BY timestamp", (server,))


def get_backtest(server: str):
    return query("SELECT timestamp, actual, predicted FROM backtest WHERE server = ? ORDER BY timestamp", (server,))


def get_anomalies(server: str):
    return query("SELECT timestamp, cpu_percent, deviation FROM anomalies WHERE server = ? ORDER BY timestamp", (server,))
