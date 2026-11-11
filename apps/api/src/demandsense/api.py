from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from demandsense.pipeline import FEATURES, history_through_origin, make_features
from demandsense.pipeline import metrics as score_metrics

ARTIFACTS = Path(
    os.getenv(
        "RETAIL_DEMAND_FORECASTING_ARTIFACTS",
        str(Path(__file__).resolve().parents[4] / "artifacts"),
    )
)
app = FastAPI(
    title="Retail Demand Forecasting API",
    version="0.1.0",
    description="Local retail forecasting, evaluation, and reliability API",
)


class HealthResponse(BaseModel):
    status: str
    artifacts_available: bool


class ProductItem(BaseModel):
    product_id: str
    description: str


class ProductPage(BaseModel):
    items: list[ProductItem]
    total: int
    limit: int
    offset: int


class HistoryPoint(BaseModel):
    week: str
    units: float


class HistoryResponse(BaseModel):
    product_id: str
    items: list[HistoryPoint]


class ForecastRecord(BaseModel):
    model_version: str | None = None
    product_id: str
    product_description: str | None = None
    forecast_origin: str
    target_week: str
    horizon: int
    predicted_units: float
    baseline_units: float
    lower_80: float | None = None
    upper_80: float | None = None
    lower_90: float | None = None
    upper_90: float | None = None


class ForecastList(BaseModel):
    items: list[ForecastRecord]


class BacktestRecord(ForecastRecord):
    actual_units: float
    absolute_error: float
    signed_error: float
    fold: str
    evaluation_fold: str | None = None


class BacktestList(BaseModel):
    items: list[BacktestRecord]


def read_json(filename: str, default: Any):
    path = ARTIFACTS / filename
    return json.loads(path.read_text()) if path.exists() else default


def load_weekly():
    path = ARTIFACTS / "weekly.parquet"
    if not path.exists():
        raise HTTPException(503, "Forecast artifacts are missing. Run the pipeline first.")
    return pd.read_parquet(path)


@app.get("/api/health", response_model=HealthResponse)
def health():
    return {
        "status": "ok",
        "artifacts_available": all(
            (ARTIFACTS / name).exists()
            for name in ("model.joblib", "weekly.parquet", "forecasts.json", "metadata.json")
        ),
    }


@app.get("/api/metadata", response_model=dict[str, Any])
def metadata():
    return read_json(
        "metadata.json",
        {"data_mode": "not configured", "message": "Run the pipeline to generate local artifacts."},
    )


@app.get("/api/dataset/quality", response_model=dict[str, Any])
def quality():
    return read_json("quality.json", {"status": "not available"})


@app.get("/api/dataset/manifest", response_model=dict[str, Any])
def dataset_manifest():
    return read_json("dataset-manifest.json", {"status": "not available"})


@app.get("/api/dataset/summary", response_model=dict[str, Any])
def summary():
    meta = metadata()
    q = quality()
    return {
        "data_mode": meta.get("data_mode"),
        "products": meta.get("products", 0),
        "weeks": meta.get("weeks", {}),
        "quality": q,
        "test_start": meta.get("test_start"),
    }


@app.get("/api/products", response_model=ProductPage)
def products(q: str = "", limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    data = load_weekly()
    items = (
        data[["StockCode", "product_description"]]
        .drop_duplicates()
        .rename(columns={"StockCode": "product_id", "product_description": "description"})
    )
    forecastable = {str(row["product_id"]) for row in read_json("forecasts.json", [])}
    if forecastable:
        items = items[items.product_id.astype(str).isin(forecastable)]
    items = items[
        items.product_id.astype(str).str.contains(q, case=False, regex=False)
        | items.description.astype(str).str.contains(q, case=False, regex=False)
    ]
    return {
        "items": items.iloc[offset : offset + limit].to_dict("records"),
        "total": len(items),
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/products/{product_id}", response_model=dict[str, Any])
def product(product_id: str):
    data = load_weekly()
    rows = data[data.StockCode.astype(str) == product_id].sort_values("week_start")
    if rows.empty:
        raise HTTPException(404, "Product not found")
    origin = pd.Timestamp(metadata().get("forecast_origin", "1900-01-01"))
    through_origin = history_through_origin(rows, origin)
    return {
        "product_id": product_id,
        "description": str(rows.product_description.iloc[0]),
        "first_observed_week": rows.week_start.min().date().isoformat(),
        "last_observed_week": rows.week_start.max().date().isoformat(),
        "observed_weeks": len(rows),
        "active_at_forecast_origin": bool(
            len(through_origin) > 0 and np.any(through_origin.to_numpy(float)[-8:] > 0)
        ),
    }


@app.get("/api/products/{product_id}/history", response_model=HistoryResponse)
def history(product_id: str):
    cutoff = pd.Timestamp(metadata().get("forecast_origin", "2262-01-01"))
    data = load_weekly()
    rows = data[
        (data.StockCode.astype(str) == product_id) & (data.week_start <= cutoff)
    ].sort_values("week_start")
    if rows.empty:
        raise HTTPException(404, "Product not found")
    series = history_through_origin(rows, cutoff)
    return {
        "product_id": product_id,
        "items": [
            {"week": pd.Timestamp(week).date().isoformat(), "units": float(units)}
            for week, units in series.items()
        ],
    }


@app.get("/api/forecasts", response_model=ForecastList)
def forecasts():
    return {"items": read_json("forecasts.json", [])}


@app.get("/api/forecasts/{product_id}", response_model=ForecastList)
def product_forecast(product_id: str):
    rows = [r for r in read_json("forecasts.json", []) if str(r["product_id"]) == product_id]
    if not rows:
        raise HTTPException(404, "Forecast not found")
    return {"product_id": product_id, "items": rows}


@app.get("/api/forecasts/{product_id}/comparison", response_model=ForecastList)
def comparison(product_id: str):
    return product_forecast(product_id)


@app.get("/api/models", response_model=list[dict[str, str]])
def models():
    return [
        {"name": "LightGBM pooled direct multi-horizon", "version": "0.1.0"},
        {"name": "Last-observation naive", "version": "baseline"},
        {"name": "Trailing 4-week mean", "version": "baseline"},
        {"name": "4-week repeating pattern", "version": "baseline"},
    ]


@app.get("/api/models/metrics", response_model=dict[str, Any])
def model_metrics():
    meta = metadata()
    scores = meta.get("metrics", {})
    chosen = meta.get("selected_baseline", "Trailing 4-week mean")
    rows = [r for r in read_json("backtests.json", []) if r.get("fold") == "final_test"]
    baseline_field = {
        "Last observation": "baseline_naive_units",
        "Trailing 4-week mean": "baseline_units",
        "4-week repeating pattern": "baseline_repeat4_units",
    }.get(chosen, "baseline_units")
    product_groups = {}
    for row in rows:
        product_groups.setdefault(row["product_id"], []).append(row)
    wins = losses = 0
    for items in product_groups.values():
        model_mae = np.mean([abs(r["actual_units"] - r["predicted_units"]) for r in items])
        base_mae = np.mean([abs(r["actual_units"] - r[baseline_field]) for r in items])
        wins += int(model_mae < base_mae)
        losses += int(model_mae > base_mae)
    ml = scores.get("LightGBM", {})
    baseline_score = scores.get(chosen, {})
    base_mae = baseline_score.get("mae")
    ml_mae = ml.get("mae")
    comparison = {
        "selected_baseline": chosen,
        "mae_difference": (ml_mae - base_mae)
        if ml_mae is not None and base_mae is not None
        else None,
        "relative_mae_improvement": ((base_mae - ml_mae) / base_mae)
        if base_mae not in (None, 0) and ml_mae is not None
        else None,
        "products_won": wins,
        "products_lost": losses,
        "product_count": len(product_groups),
    }
    return {**scores, "comparison": comparison}


def grouped_metrics(group_key: str):
    rows = [r for r in read_json("backtests.json", []) if r.get("fold") == "final_test"]
    chosen = metadata().get("selected_baseline", "Trailing 4-week mean")
    baseline_field = {
        "Last observation": "baseline_naive_units",
        "Trailing 4-week mean": "baseline_units",
        "4-week repeating pattern": "baseline_repeat4_units",
    }.get(chosen, "baseline_units")
    result = []
    grouped = {}
    for row in rows:
        grouped.setdefault(str(row[group_key]), []).append(row)
    for key, items in sorted(grouped.items()):
        actual = [r["actual_units"] for r in items]
        result.append(
            {
                group_key: key,
                "LightGBM": score_metrics(actual, [r["predicted_units"] for r in items]),
                chosen: score_metrics(actual, [r[baseline_field] for r in items]),
            }
        )
    return {"selected_baseline": chosen, "items": result}


@app.get("/api/models/metrics/by-horizon", response_model=dict[str, Any])
def metrics_by_horizon():
    return grouped_metrics("horizon")


@app.get("/api/models/metrics/by-product", response_model=dict[str, Any])
def metrics_by_product():
    return grouped_metrics("product_id")


@app.get("/api/backtests", response_model=BacktestList)
def backtests():
    return {"items": read_json("backtests.json", [])}


@app.get("/api/backtests/{product_id}", response_model=BacktestList)
def product_backtest(product_id: str):
    return {
        "items": [r for r in read_json("backtests.json", []) if str(r["product_id"]) == product_id]
    }


@app.get("/api/intervals/coverage", response_model=dict[str, Any])
def coverage():
    rows = [r for r in read_json("backtests.json", []) if r.get("fold") == "final_test"]
    if not rows:
        return {"status": "unavailable", "reason": "No final holdout results"}

    def coverage_for(items, level):
        return (
            sum(r[f"lower_{level}"] <= r["actual_units"] <= r[f"upper_{level}"] for r in items)
            / len(items)
            if items
            else None
        )

    by_horizon = []
    for h in range(1, 5):
        items = [r for r in rows if r["horizon"] == h]
        by_horizon.append(
            {
                "horizon": h,
                "count": len(items),
                "observed_80": coverage_for(items, "80"),
                "observed_90": coverage_for(items, "90"),
                "mean_width_80": float(np.mean([r["upper_80"] - r["lower_80"] for r in items]))
                if items
                else None,
                "mean_width_90": float(np.mean([r["upper_90"] - r["lower_90"] for r in items]))
                if items
                else None,
            }
        )
    by_product = []
    for sku in sorted({r["product_id"] for r in rows}):
        items = [r for r in rows if r["product_id"] == sku]
        if len(items) >= 4:
            by_product.append(
                {
                    "product_id": sku,
                    "count": len(items),
                    "observed_80": coverage_for(items, "80"),
                    "observed_90": coverage_for(items, "90"),
                }
            )
    return {
        "count": len(rows),
        "nominal_80": 0.8,
        "observed_80": coverage_for(rows, "80"),
        "nominal_90": 0.9,
        "observed_90": coverage_for(rows, "90"),
        "mean_width_80": float(np.mean([r["upper_80"] - r["lower_80"] for r in rows])),
        "mean_width_90": float(np.mean([r["upper_90"] - r["lower_90"] for r in rows])),
        "by_horizon": by_horizon,
        "by_product": by_product,
    }


@app.get("/api/features/importance", response_model=dict[str, Any])
def importance():
    items = metadata().get("feature_importance", [])
    total = sum(item.get("gain", 0.0) for item in items)
    return {
        "items": [
            {**item, "relative_importance": item.get("gain", 0.0) / total if total > 0 else 0.0}
            for item in items[:10]
        ]
    }


class Scenario(BaseModel):
    product_id: str
    adjustment_pct: float = Field(ge=-50, le=100)
    window_weeks: Literal[2, 4, 8] = 4
    shock_type: Literal["sustained", "one-time"] = "sustained"


@app.post("/api/simulations/demand-shift", response_model=dict[str, Any])
def simulate(body: Scenario):
    model_path = ARTIFACTS / "model.joblib"
    if not model_path.exists():
        raise HTTPException(503, "Model artifact is missing. Run the pipeline first.")
    data = load_weekly()
    g = data[data.StockCode.astype(str) == body.product_id].sort_values("week_start")
    if g.empty:
        raise HTTPException(404, "Product not found")
    origin = pd.Timestamp(metadata().get("forecast_origin", "1900-01-01"))
    observed = history_through_origin(g, origin)
    if len(observed) < 8 or not np.any(observed.to_numpy(float)[-8:] > 0):
        raise HTTPException(
            422, "Product had no positive sale in the eight weeks before the selected origin"
        )
    hist = observed.to_numpy(float)
    changed = hist.copy()
    n = min(body.window_weeks, len(hist))
    factor = 1 + body.adjustment_pct / 100
    if body.shock_type == "one-time":
        changed[-1] *= factor
    elif body.shock_type == "sustained":
        changed[-n:] *= factor
    else:
        raise HTTPException(422, "shock_type must be sustained or one-time")
    model = joblib.load(model_path)
    forecasts = []
    changed_features = []
    demand_features = [
        "lag_1",
        "lag_2",
        "lag_3",
        "lag_4",
        "lag_8",
        "mean_2",
        "mean_4",
        "mean_8",
        "std_4",
        "max_4",
        "min_4",
        "zero_weeks_8",
        "weeks_since_sale",
    ]
    reference = {name: [] for name in demand_features}
    values = hist
    for pos in range(8, len(values)):
        past_origin = pd.Timestamp(observed.index[pos - 1])
        past_target = pd.Timestamp(observed.index[pos])
        sample = make_features(values[:pos], past_origin, past_target, 1, pos)
        for name in demand_features:
            reference[name].append(sample[name])
    for h in range(1, 5):
        target = origin + pd.Timedelta(days=7 * h)
        base = make_features(hist, origin, target, h, len(hist))
        altered = make_features(changed, origin, target, h, len(hist))
        code = metadata().get("product_code_map", {}).get(body.product_id)
        if code is None:
            raise HTTPException(404, "Product is not part of the frozen model cohort")
        base["product_code"] = altered["product_code"] = code
        if h == 1:
            changed_features = [
                {"feature": name, "before": base[name], "after": altered[name]}
                for name in demand_features
                if base[name] != altered[name]
            ]
        a = float(model.predict(pd.DataFrame([base], columns=FEATURES))[0])
        b = float(model.predict(pd.DataFrame([altered], columns=FEATURES))[0])
        if metadata().get("target_transform") == "log1p":
            a = float(np.expm1(a))
            b = float(np.expm1(b))
        a = max(0.0, a)
        b = max(0.0, b)
        forecasts.append(
            {"horizon": h, "original_units": a, "simulated_units": b, "change_units": b - a}
        )
    out_of_range = []
    for item in changed_features:
        samples = reference[item["feature"]]
        if samples:
            low, high = np.quantile(samples, [0.05, 0.95]).tolist()
            item["historical_p05"] = float(low)
            item["historical_p95"] = float(high)
            item["outside_historical_range"] = item["after"] < low or item["after"] > high
            if item["outside_historical_range"]:
                out_of_range.append(item["feature"])
        else:
            item["outside_historical_range"] = None
    calibration = metadata().get("interval_calibration", {})
    return {
        "product_id": body.product_id,
        "adjustment_pct": body.adjustment_pct,
        "window_weeks": n,
        "shock_type": body.shock_type,
        "items": forecasts,
        "changed_features": changed_features,
        "out_of_range_features": out_of_range,
        "interval_calibration": {
            "method": calibration.get("method"),
            "validation_samples": calibration.get("samples", 0),
            "scenario_coverage_measured": False,
            "note": "Calibration uses unperturbed validation residuals; scenario coverage is not measured.",
        },
        "interpretation": "Scenario sensitivity only; hypothetical outputs have no known future ground truth or accuracy estimate. Feature ranges are descriptive historical 5th–95th percentiles, not reliability probabilities.",
    }
