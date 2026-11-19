"""Step 2 - Forecast future CPU usage with XGBoost.

XGBoost only understands tables of numbers, so we turn a time series into columns
("features"): hour of day, day of week, usage 24h ago, usage 1 week ago, recent averages.
Then we forecast one hour at a time and feed each prediction back in as history
(this is called recursive forecasting).
"""
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error
from config import BACKTEST_HOURS, HORIZON_HOURS

try:
    from xgboost import XGBRegressor

    MODEL_NAME = "XGBoost"

    def make_model():
        return XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=4,
                            subsample=0.9, colsample_bytree=0.9, random_state=42)
except ImportError:  # lets the code run even if xgboost isn't installed yet
    from sklearn.ensemble import HistGradientBoostingRegressor

    MODEL_NAME = "GradientBoosting (xgboost not installed)"
    print("WARNING: xgboost not installed - using scikit-learn gradient boosting instead. "
          "Run: pip install xgboost")

    def make_model():
        return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05,
                                             max_depth=4, random_state=42)

FEATURES = ["hour", "dayofweek", "is_weekend", "lag_24", "lag_168", "roll_24", "roll_168"]


def build_features(y: pd.Series) -> pd.DataFrame:
    """Turn an hourly CPU series (indexed by timestamp) into a feature table."""
    idx = y.index
    df = pd.DataFrame({"y": y.values}, index=idx)
    df["hour"] = idx.hour
    df["dayofweek"] = idx.dayofweek
    df["is_weekend"] = (idx.dayofweek >= 5).astype(int)
    df["lag_24"] = y.shift(24).values            # same hour yesterday
    df["lag_168"] = y.shift(168).values          # same hour last week
    df["roll_24"] = y.shift(1).rolling(24).mean().values    # average of last 24h
    df["roll_168"] = y.shift(1).rolling(168).mean().values  # average of last 7 days
    return df.dropna()


def _recursive_forecast(model, y_hist: pd.Series, horizon: int) -> pd.Series:
    """Predict `horizon` hours ahead, one hour at a time."""
    vals = list(y_hist.values)
    ts = y_hist.index[-1]
    stamps, preds = [], []
    for _ in range(horizon):
        ts = ts + pd.Timedelta(hours=1)
        row = {
            "hour": ts.hour, "dayofweek": ts.dayofweek, "is_weekend": int(ts.dayofweek >= 5),
            "lag_24": vals[-24], "lag_168": vals[-168],
            "roll_24": float(np.mean(vals[-24:])), "roll_168": float(np.mean(vals[-168:])),
        }
        pred = float(np.clip(model.predict(pd.DataFrame([row], columns=FEATURES))[0], 0, 100))
        vals.append(pred)
        stamps.append(ts)
        preds.append(pred)
    return pd.Series(preds, index=pd.DatetimeIndex(stamps))


def train_and_forecast(y: pd.Series, horizon: int = HORIZON_HOURS,
                       test_hours: int = BACKTEST_HOURS) -> dict:
    """
    1. BACKTEST: train on everything except the last week, forecast that week, compare
       with what really happened -> honest accuracy (MAE = average error in CPU % points).
    2. FINAL: retrain on all the data and forecast the unseen future.
    """
    if len(y) < 168 + test_hours + 48:
        raise ValueError(f"Need at least {168 + test_hours + 48} hourly rows, got {len(y)}")

    cut = len(y) - test_hours
    train_y, actual = y.iloc[:cut], y.iloc[cut:]

    model = make_model()
    feats = build_features(train_y)
    model.fit(feats[FEATURES], feats["y"])
    backtest_pred = _recursive_forecast(model, train_y, test_hours)

    mae = float(mean_absolute_error(actual.values, backtest_pred.values))
    # Baseline "seasonal naive": just repeat last week. The AI should beat this.
    baseline_mae = float(mean_absolute_error(actual.values, y.shift(168).iloc[cut:].values))

    final = make_model()
    feats_all = build_features(y)
    final.fit(feats_all[FEATURES], feats_all["y"])
    future = _recursive_forecast(final, y, horizon)

    return {
        "forecast": future,
        "backtest": pd.DataFrame({"actual": actual.values, "predicted": backtest_pred.values},
                                 index=actual.index),
        "mae": mae,
        "baseline_mae": baseline_mae,
        "model_name": MODEL_NAME,
    }
