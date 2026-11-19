"""Tiny SQLite helper. Tables are rewritten on every pipeline run (fine for a prototype)."""
import sqlite3
import pandas as pd
from config import DB_PATH


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def save_table(df: pd.DataFrame, name: str):
    with get_conn() as con:
        df.to_sql(name, con, if_exists="replace", index=False)


def query(sql: str, params: tuple = ()) -> list[dict]:
    """Run a SELECT and return a list of dicts. Returns [] if the table doesn't exist yet."""
    try:
        with get_conn() as con:
            return pd.read_sql(sql, con, params=params).to_dict("records")
    except Exception:
        return []
