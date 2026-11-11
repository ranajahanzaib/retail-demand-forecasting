"""Auditable transaction preparation and leakage-aware weekly forecasting."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REQUIRED = [
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
]
FEATURES = [
    "product_code",
    "horizon",
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
    "age_weeks",
    "target_month",
    "target_quarter",
]


def load_transactions(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    frame = pd.read_excel(p) if p.suffix.lower() in {".xls", ".xlsx"} else pd.read_csv(p)
    frame.columns = [str(c).strip() for c in frame.columns]
    missing = sorted(set(REQUIRED) - set(frame.columns))
    if missing:
        raise ValueError(f"Source is missing required columns: {', '.join(missing)}")
    return frame


def prepare_transactions(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    df = raw.copy()
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")
    source_dates = df["InvoiceDate"].copy()
    parsed_dates = pd.to_datetime(source_dates, errors="coerce", format="mixed")
    day_first_dates = source_dates.astype("string").str.match(
        r"^\s*\d{1,2}/\d{1,2}/\d{4}(?:\s|$)", na=False
    )
    if day_first_dates.any():
        parsed_dates.loc[day_first_dates] = pd.to_datetime(
            source_dates.loc[day_first_dates], errors="coerce", format="mixed", dayfirst=True
        )
    df["InvoiceDate"] = parsed_dates
    cancellation = (
        df["InvoiceNo"].astype("string").str.strip().str.upper().str.startswith("C", na=False)
    )
    invalid_date = df["InvoiceDate"].isna()
    missing_invoice = df["InvoiceNo"].isna() | (df["InvoiceNo"].astype("string").str.strip() == "")
    nonnumeric_qty = df["Quantity"].isna()
    nonfinite_qty = ~np.isfinite(df["Quantity"].fillna(0))
    zero_qty = df["Quantity"].eq(0)
    negative_qty = df["Quantity"].lt(0)
    invalid_qty = df["Quantity"].isna() | nonfinite_qty | (df["Quantity"] <= 0)
    invalid_price = (
        df["UnitPrice"].isna() | ~np.isfinite(df["UnitPrice"].fillna(0)) | (df["UnitPrice"] <= 0)
    )
    missing_sku = df["StockCode"].isna() | (df["StockCode"].astype("string").str.strip() == "")
    missing_description = df["Description"].isna() | (
        df["Description"].astype("string").str.strip() == ""
    )
    # Conservatively remove only known postage/administrative codes.
    admin = (
        df["StockCode"]
        .astype("string")
        .str.upper()
        .str.strip()
        .isin({"POST", "DOT", "M", "C2", "BANK CHARGES"})
    )
    keep = ~(
        cancellation
        | invalid_date
        | missing_invoice
        | invalid_qty
        | invalid_price
        | missing_sku
        | admin
    )
    accepted = df.loc[keep].copy()
    description_transforms = int(missing_description.loc[keep].sum())
    accepted["StockCode"] = accepted["StockCode"].astype(str).str.strip()
    accepted["Description"] = (
        accepted["Description"]
        .where(~missing_description.loc[keep], "Description unavailable")
        .astype(str)
        .str.strip()
    )
    accepted["revenue"] = accepted["Quantity"] * accepted["UnitPrice"]
    if not np.isfinite(accepted["revenue"]).all():
        raise ValueError(
            "Quantity × UnitPrice overflowed a finite numeric value; inspect the source rows."
        )
    accepted["week_start"] = (
        accepted["InvoiceDate"].dt.to_period("W-SUN").dt.start_time.dt.normalize()
    )
    dupcols = [
        c for c in ["InvoiceNo", "StockCode", "Quantity", "InvoiceDate", "UnitPrice"] if c in df
    ]
    quality = {
        "original_rows": len(df),
        "accepted_positive_sales_rows": len(accepted),
        "excluded_rows": int((~keep).sum()),
        "transformed_description_rows": description_transforms,
        "cancellation_rows": int(cancellation.sum()),
        "invalid_date_rows": int(invalid_date.sum()),
        "missing_invoice_id_rows": int(missing_invoice.sum()),
        "invalid_quantity_rows": int(invalid_qty.sum()),
        "nonnumeric_quantity_rows": int(nonnumeric_qty.sum()),
        "nonfinite_quantity_rows": int(nonfinite_qty.sum()),
        "zero_quantity_rows": int(zero_qty.sum()),
        "negative_quantity_rows": int(negative_qty.sum()),
        "invalid_price_rows": int(invalid_price.sum()),
        "missing_product_id_rows": int(missing_sku.sum()),
        "administrative_rows": int(admin.sum()),
        "duplicate_candidates": int(df.duplicated(dupcols, keep=False).sum()),
        "missing_customer_ids": int(df["CustomerID"].isna().sum()),
        "missing_field_counts": {str(column): int(df[column].isna().sum()) for column in REQUIRED},
        "products": int(accepted["StockCode"].nunique()),
        "date_min": accepted["InvoiceDate"].min().date().isoformat() if len(accepted) else None,
        "date_max": accepted["InvoiceDate"].max().date().isoformat() if len(accepted) else None,
        "retention_pct": round(100 * len(accepted) / len(df), 2) if len(df) else None,
        "gross_positive_units": float(accepted["Quantity"].sum()),
        "gross_positive_revenue": float(accepted["revenue"].sum()),
        "target_definition": "Gross positive units; cancellations and nonpositive quantities excluded.",
    }
    return accepted, quality


def weekly_series(tx: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    if tx.empty:
        raise ValueError("No accepted transactions remain after cleaning")
    grouped = tx.groupby(["StockCode", "week_start"], as_index=False).agg(
        weekly_units_sold=("Quantity", "sum"),
        weekly_revenue=("revenue", "sum"),
        transaction_lines=("InvoiceNo", "count"),
        active_days=("InvoiceDate", lambda s: s.dt.date.nunique()),
        average_unit_price=("UnitPrice", "mean"),
        product_description=("Description", "first"),
    )
    # Exclude incomplete dataset boundary weeks and fill only inside each product's observed span.
    first_date = tx["InvoiceDate"].min().normalize()
    start = tx["week_start"].min() + (
        pd.Timedelta(days=7) if first_date.weekday() > 0 else pd.Timedelta(days=0)
    )
    end = tx["week_start"].max()
    end_date = tx["InvoiceDate"].max().normalize()
    if end_date.weekday() < 6:
        end -= pd.Timedelta(days=7)
    grouped = grouped[(grouped.week_start >= start) & (grouped.week_start <= end)]
    rows = []
    for sku, product in grouped.groupby("StockCode"):
        product = product.set_index("week_start").sort_index()
        if product.empty:
            continue
        idx = pd.date_range(product.index.min(), product.index.max(), freq="7D")
        product = product.reindex(idx)
        product.index.name = "week_start"
        product["StockCode"] = sku
        product["weekly_units_sold"] = product["weekly_units_sold"].fillna(0)
        product["weekly_revenue"] = product["weekly_revenue"].fillna(0)
        product["transaction_lines"] = product["transaction_lines"].fillna(0)
        product["active_days"] = product["active_days"].fillna(0)
        product["product_description"] = product["product_description"].ffill().bfill()
        rows.append(product.reset_index())
    out = pd.concat(rows, ignore_index=True) if rows else grouped
    meta = {
        "complete_week_start": str(start.date()),
        "complete_week_end": str(end.date()),
        "weekly_rows": len(out),
    }
    return out, meta


def make_features(
    history: np.ndarray | list[float] | pd.Series,
    origin: pd.Timestamp,
    target_week: pd.Timestamp,
    horizon: int,
    age: int = 0,
) -> dict[str, float | int]:
    if isinstance(history, pd.Series) and isinstance(history.index, pd.DatetimeIndex):
        history = history.loc[history.index <= pd.Timestamp(origin)]
    x = np.asarray(history, dtype=float)

    def lag(k: int) -> float:
        return float(x[-k]) if len(x) >= k else 0.0

    last8 = x[-8:]
    last4 = x[-4:]
    positive_ago = next((i for i, value in enumerate(x[::-1]) if value > 0), len(x))
    return {
        "horizon": horizon,
        "lag_1": lag(1),
        "lag_2": lag(2),
        "lag_3": lag(3),
        "lag_4": lag(4),
        "lag_8": lag(8),
        "mean_2": float(np.mean(x[-2:])) if len(x) else 0.0,
        "mean_4": float(np.mean(last4)) if len(last4) else 0.0,
        "mean_8": float(np.mean(last8)) if len(last8) else 0.0,
        "std_4": float(np.std(last4)) if len(last4) > 1 else 0.0,
        "max_4": float(np.max(last4)) if len(last4) else 0.0,
        "min_4": float(np.min(last4)) if len(last4) else 0.0,
        "zero_weeks_8": float(np.sum(last8 == 0)),
        "weeks_since_sale": float(positive_ago),
        "age_weeks": age,
        "target_month": target_week.month,
        "target_quarter": target_week.quarter,
    }


def baseline(history: np.ndarray, horizon: int, name: str) -> float:
    if name == "naive":
        return float(history[-1]) if len(history) else 0.0
    if name == "mean4":
        return float(np.mean(history[-4:])) if len(history) else 0.0
    if name == "repeat4":
        return (
            float(history[-(4 - horizon + 1)])
            if len(history) >= (4 - horizon + 1)
            else (float(np.mean(history[-4:])) if len(history) else 0.0)
        )
    raise ValueError(f"Unknown baseline {name}")


def metrics(actual: list[float], predicted: list[float]) -> dict[str, Any]:
    a, p = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    den = float(np.abs(a).sum())
    wape = float(np.abs(a - p).sum() / den) if den > 0 else None
    return {
        "mae": float(np.mean(np.abs(a - p))) if len(a) else None,
        "wape": wape,
        "wape_percent": wape * 100 if wape is not None else None,
        "wape_unavailable_reason": None
        if wape is not None
        else "Actual unit denominator is zero or no observations are available.",
        "bias": float(np.mean(p - a)) if len(a) else None,
        "count": len(a),
    }


def examples_through_cutoff(examples: list[tuple], cutoff: pd.Timestamp) -> list[tuple]:
    """Keep training labels available no later than the fold's training cutoff."""
    cutoff = pd.Timestamp(cutoff)
    return [example for example in examples if pd.Timestamp(example[1]) <= cutoff]


def validation_origins(
    weeks: list[pd.Timestamp],
    validation_start: pd.Timestamp,
    test_start: pd.Timestamp,
    horizon_weeks: int = 4,
) -> list[pd.Timestamp]:
    """Return origins whose entire validation horizon ends before the final holdout."""
    last_validation_target = pd.Timestamp(test_start) - pd.Timedelta(days=7)
    return [
        pd.Timestamp(week)
        for week in weeks
        if pd.Timestamp(week) >= pd.Timestamp(validation_start)
        and pd.Timestamp(week) + pd.Timedelta(days=7 * horizon_weeks) <= last_validation_target
    ]


def finite_sample_quantile(errors: list[float] | np.ndarray, coverage: float) -> float | None:
    """Conformal-style higher order statistic with finite-sample rank correction."""
    values = np.sort(np.asarray(errors, dtype=float))
    if not len(values):
        return None
    rank = min(len(values), max(1, math.ceil((len(values) + 1) * coverage)))
    return float(values[rank - 1])


def select_product_cohort(
    weekly: pd.DataFrame, selection_cutoff: pd.Timestamp, maximum: int = 40
) -> tuple[list[str], pd.DataFrame]:
    """Freeze SKU selection using only the initial training window."""
    selection = weekly[weekly.week_start < pd.Timestamp(selection_cutoff)]
    ranked = selection.groupby("StockCode").agg(
        rows=("weekly_units_sold", "size"),
        units=("weekly_units_sold", "sum"),
        zero_share=("weekly_units_sold", lambda values: float((values == 0).mean())),
    )
    ranked = ranked.query("rows >= 8 and units > 0").sort_values(
        "units", ascending=False, kind="stable"
    )
    cohort = ranked.index[: max(0, maximum - 1)].tolist()
    sparse = ranked[ranked.zero_share > 0]
    sparse = sparse.loc[~sparse.index.isin(cohort)].sort_values(
        ["zero_share", "units"], ascending=[False, True], kind="stable"
    )
    if len(sparse):
        cohort.append(sparse.index[0])
    else:
        cohort = ranked.index[:maximum].tolist()
    if not cohort:
        raise ValueError(
            "No products meet the pre-test eligibility rule (8 complete weeks and positive units)."
        )
    return cohort, ranked


def history_through_origin(product: pd.DataFrame, origin: pd.Timestamp) -> pd.Series:
    """Return weekly observed units through origin, padding only the known past."""
    past = product[product.week_start <= pd.Timestamp(origin)].sort_values("week_start")
    if past.empty:
        return pd.Series(dtype=float)
    index = pd.date_range(past.week_start.min(), pd.Timestamp(origin), freq="7D")
    return past.set_index("week_start").weekly_units_sold.reindex(index).fillna(0.0)


def run_pipeline(
    raw: pd.DataFrame,
    output: Path,
    source_sha256: str | None = None,
    data_mode: str = "local transaction data",
) -> dict[str, Any]:
    import joblib
    from lightgbm import LGBMRegressor

    tx, quality = prepare_transactions(raw)
    weekly, period = weekly_series(tx)
    if weekly.empty:
        raise ValueError("No complete weeks are available")
    # Freeze product cohort using only an early window. Keep a bounded, inspectable sample.
    weeks = sorted(weekly.week_start.unique())
    if len(weeks) < 20:
        raise ValueError(
            "At least 20 complete weeks are required for an initial selection window, rolling validation, and four-week holdout."
        )
    test_start = pd.Timestamp(weeks[-4])
    selection_index = max(8, int(len(weeks) * 0.5))
    selection_cutoff = pd.Timestamp(weeks[selection_index])
    cohort, ranked = select_product_cohort(weekly, selection_cutoff)
    product_codes = {sku: index for index, sku in enumerate(sorted(cohort, key=str))}
    frame = weekly[weekly.StockCode.isin(cohort)].copy()
    # Validation origins are pre-test. Labels remain strictly after feature origin and before test.
    validation_start = max(selection_cutoff, pd.Timestamp(weeks[max(0, len(weeks) - 16)]))
    origins = validation_origins(weeks, validation_start, test_start)
    if not origins:
        raise ValueError("No rolling validation origin remains after the cohort selection cutoff.")
    all_examples = []
    for sku, g in frame.groupby("StockCode"):
        g = g.sort_values("week_start")
        for pos in range(8, len(g)):
            origin = pd.Timestamp(g.iloc[pos - 1].week_start)
            if origin >= test_start:
                continue
            hist = g.iloc[:pos].weekly_units_sold.to_numpy(float)
            for h in range(1, 5):
                target_pos = pos + h - 1
                if (
                    target_pos >= len(g)
                    or pd.Timestamp(g.iloc[target_pos].week_start) >= test_start
                ):
                    continue
                feat = make_features(
                    hist, origin, pd.Timestamp(g.iloc[target_pos].week_start), h, pos
                )
                feat["product_code"] = product_codes[sku]
                all_examples.append(
                    (
                        origin,
                        pd.Timestamp(g.iloc[target_pos].week_start),
                        feat,
                        float(g.iloc[target_pos].weekly_units_sold),
                    )
                )
    if not all_examples:
        raise ValueError(
            "Not enough pre-test history to train. Need at least eight complete weeks per product."
        )

    def fit_model(examples, log_target: bool = False):
        candidate = LGBMRegressor(
            objective="regression",
            n_estimators=120,
            learning_rate=0.035,
            max_depth=4,
            num_leaves=12,
            min_child_samples=12,
            reg_lambda=2.0,
            random_state=42,
            verbosity=-1,
            n_jobs=1,
            deterministic=True,
        )
        labels = np.asarray([r[3] for r in examples])
        candidate.fit(
            pd.DataFrame([r[2] for r in examples], columns=FEATURES),
            np.log1p(labels) if log_target else labels,
            categorical_feature=["product_code"],
        )
        return candidate

    def predict_units(candidate, features, log_target: bool) -> float:
        value = float(candidate.predict(pd.DataFrame([features], columns=FEATURES))[0])
        return max(0.0, float(np.expm1(value))) if log_target else max(0.0, value)

    # Each calibration fold is trained only on labels available at that fold's origin.
    val_actual, val_pred_raw, val_pred_log, val_horizons = [], [], [], []
    validation_records = []
    validation_baselines = {
        name: {"actual": [], "predicted": []} for name in ("naive", "mean4", "repeat4")
    }
    for origin in origins:
        eligible = examples_through_cutoff(all_examples, origin)
        if not eligible:
            continue
        fold_model_raw = fit_model(eligible, False)
        fold_model_log = fit_model(eligible, True)
        for sku, g in frame.groupby("StockCode"):
            g = g.sort_values("week_start")
            available = history_through_origin(g, origin)
            future = g[
                (g.week_start > origin)
                & (g.week_start <= origin + pd.Timedelta(days=28))
                & (g.week_start < test_start)
            ]
            if not len(available):
                continue
            hist = available.to_numpy(float)
            if not np.any(hist[-8:] > 0):
                continue
            for _, row in future.iterrows():
                h = int((pd.Timestamp(row.week_start) - origin).days // 7)
                if h not in range(1, 5):
                    continue
                feat = make_features(hist, origin, pd.Timestamp(row.week_start), h, len(hist))
                feat["product_code"] = product_codes[sku]
                predicted_raw = predict_units(fold_model_raw, feat, False)
                predicted_log = predict_units(fold_model_log, feat, True)
                actual = float(row.weekly_units_sold)
                val_pred_raw.append(predicted_raw)
                val_pred_log.append(predicted_log)
                val_actual.append(actual)
                val_horizons.append(h)
                for name in validation_baselines:
                    validation_baselines[name]["actual"].append(float(row.weekly_units_sold))
                    validation_baselines[name]["predicted"].append(baseline(hist, h, name))
                validation_records.append(
                    {
                        "model_version": "0.1.0",
                        "product_id": str(sku),
                        "forecast_origin": origin.date().isoformat(),
                        "target_week": pd.Timestamp(row.week_start).date().isoformat(),
                        "horizon": h,
                        "actual_units": actual,
                        "predicted_raw_units": predicted_raw,
                        "predicted_log_units": predicted_log,
                        "baseline_units": baseline(hist, h, "mean4"),
                        "fold": "validation",
                        "evaluation_fold": f"validation_{origin.date().isoformat()}",
                    }
                )
    raw_validation = metrics(val_actual, val_pred_raw)
    log_validation = metrics(val_actual, val_pred_log)
    use_log_target = (
        log_validation["mae"] is not None
        and raw_validation["mae"] is not None
        and log_validation["mae"] < raw_validation["mae"]
    )
    val_pred = val_pred_log if use_log_target else val_pred_raw
    validation_backtests = []
    for row in validation_records:
        row["predicted_units"] = row.pop(
            "predicted_log_units" if use_log_target else "predicted_raw_units"
        )
        row.pop("predicted_raw_units" if use_log_target else "predicted_log_units")
        row["absolute_error"] = abs(row["actual_units"] - row["predicted_units"])
        row["signed_error"] = row["predicted_units"] - row["actual_units"]
        validation_backtests.append(row)
    residuals = np.abs(np.asarray(val_actual) - np.asarray(val_pred))
    global_q80 = finite_sample_quantile(residuals, 0.8) or 0.0
    global_q90 = finite_sample_quantile(residuals, 0.9) or 0.0
    calibration_by_horizon = {}
    for h in range(1, 5):
        h_errors = residuals[np.asarray(val_horizons) == h]
        if len(h_errors) >= 20:
            calibration_by_horizon[str(h)] = {
                "samples": len(h_errors),
                "q80": finite_sample_quantile(h_errors, 0.8),
                "q90": finite_sample_quantile(h_errors, 0.9),
                "source": "horizon-specific validation residuals",
            }
        else:
            calibration_by_horizon[str(h)] = {
                "samples": len(h_errors),
                "q80": global_q80,
                "q90": global_q90,
                "source": "global validation residual fallback",
            }
    forecast_origin = test_start - pd.Timedelta(days=7)
    # Final model is fitted only on pre-test labels.
    final_examples = examples_through_cutoff(all_examples, forecast_origin)
    model = fit_model(final_examples, use_log_target)
    # Predict the untouched final four-week holdout.
    forecasts, bt = [], []
    for sku, g in frame.groupby("StockCode"):
        g = g.sort_values("week_start").reset_index(drop=True)
        history = history_through_origin(g, forecast_origin)
        # Use only information through origin and require a positive sale in its recent eight weeks.
        if len(history) < 8 or not np.any(history.to_numpy(float)[-8:] > 0):
            continue
        hist = history.to_numpy(float)
        origin = forecast_origin
        for h in range(1, 5):
            q80 = calibration_by_horizon[str(h)]["q80"]
            q90 = calibration_by_horizon[str(h)]["q90"]
            target = test_start + pd.Timedelta(days=7 * (h - 1))
            feat = make_features(hist, origin, target, h, len(hist))
            feat["product_code"] = product_codes[sku]
            pred = predict_units(model, feat, use_log_target)
            base = baseline(hist, h, "mean4")
            description = (
                g.product_description.dropna().iloc[0]
                if g.product_description.notna().any()
                else "Description unavailable"
            )
            forecasts.append(
                {
                    "model_version": "0.1.0",
                    "product_id": str(sku),
                    "product_description": str(description),
                    "forecast_origin": origin.date().isoformat(),
                    "target_week": target.date().isoformat(),
                    "horizon": h,
                    "predicted_units": pred,
                    "baseline_units": base,
                    "baseline_naive_units": baseline(hist, h, "naive"),
                    "baseline_repeat4_units": baseline(hist, h, "repeat4"),
                    "lower_80": max(0.0, pred - float(q80)),
                    "upper_80": pred + float(q80),
                    "lower_90": max(0.0, pred - float(q90)),
                    "upper_90": pred + float(q90),
                }
            )
            obs = g[g.week_start == target]
            if len(obs):
                actual = float(obs.weekly_units_sold.iloc[0])
                bt.append(
                    {
                        **forecasts[-1],
                        "model_version": "0.1.0",
                        "actual_units": actual,
                        "absolute_error": abs(actual - pred),
                        "signed_error": pred - actual,
                        "fold": "final_test",
                        "evaluation_fold": "final_test",
                    }
                )
    base_names = {
        "Last observation": "naive",
        "Trailing 4-week mean": "mean4",
        "4-week repeating pattern": "repeat4",
    }
    holdout_actual = [r["actual_units"] for r in bt]
    holdout_pred = [r["predicted_units"] for r in bt]
    holdout_metrics = {"LightGBM": metrics(holdout_actual, holdout_pred)}
    baseline_fields = {
        "Last observation": "baseline_naive_units",
        "Trailing 4-week mean": "baseline_units",
        "4-week repeating pattern": "baseline_repeat4_units",
    }
    for label, name in base_names.items():
        holdout_metrics[label] = metrics(holdout_actual, [r[baseline_fields[label]] for r in bt])
    baseline_validation = {
        name: metrics(values["actual"], values["predicted"])
        for name, values in validation_baselines.items()
    }
    selected_baseline_key = min(
        (name for name, scores in baseline_validation.items() if scores["mae"] is not None),
        key=lambda name: baseline_validation[name]["mae"],
        default="mean4",
    )
    baseline_labels = {
        "naive": "Last observation",
        "mean4": "Trailing 4-week mean",
        "repeat4": "4-week repeating pattern",
    }
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    source_hash = (
        source_sha256
        or hashlib.sha256(pd.util.hash_pandas_object(raw, index=True).values.tobytes()).hexdigest()
    )
    joblib.dump(model, out / "model.joblib")
    weekly.to_parquet(out / "weekly.parquet", index=False)
    pd.DataFrame(forecasts).to_json(out / "forecasts.json", orient="records", indent=2)
    pd.DataFrame(validation_backtests + bt).to_json(
        out / "backtests.json", orient="records", indent=2
    )
    (out / "quality.json").write_text(json.dumps(quality, indent=2, allow_nan=False))
    is_uci = data_mode.lower().startswith("uci")
    (out / "dataset-manifest.json").write_text(
        json.dumps(
            {
                "data_mode": data_mode,
                "source_url": "https://archive.ics.uci.edu/dataset/352/online+retail"
                if is_uci
                else None,
                "dataset_doi": "10.24432/C5BW33" if is_uci else None,
                "source_sha256": source_hash,
                "ingested_at_utc": datetime.now(UTC).isoformat(),
                "original_row_count": len(raw),
                "accepted_row_count": len(tx),
                "cleaning_configuration": {
                    "target": "gross positive units",
                    "exclude_cancellations": True,
                    "exclude_nonpositive_quantity": True,
                    "exclude_nonpositive_price": True,
                    "exclude_missing_invoice_id": True,
                    "administrative_codes": ["POST", "DOT", "M", "C2", "BANK CHARGES"],
                    "deduplicate": False,
                },
            },
            indent=2,
            allow_nan=False,
        )
    )
    model_config = {
        "objective": "regression",
        "n_estimators": 120,
        "learning_rate": 0.035,
        "max_depth": 4,
        "num_leaves": 12,
        "min_child_samples": 12,
        "reg_lambda": 2.0,
        "random_state": 42,
        "n_jobs": 1,
        "deterministic": True,
    }
    run_config = {
        "model": model_config,
        "target_transform": "log1p" if use_log_target else "identity",
        "selection_window_fraction": 0.5,
        "minimum_history_weeks": 8,
        "cohort_limit": 40,
        "forecast_horizon": 4,
        "final_holdout_weeks": 4,
    }
    config_hash = hashlib.sha256(
        json.dumps(run_config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    try:
        code_version = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[4],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        working_tree_dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=Path(__file__).resolve().parents[4],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        )
    except (OSError, subprocess.CalledProcessError):
        code_version = None
        working_tree_dirty = None
    (out / "metadata.json").write_text(
        json.dumps(
            {
                "data_mode": data_mode,
                "model_id": "retail-demand-forecasting-lightgbm-v0.1",
                "model_version": "0.1.0",
                "trained_at_utc": datetime.now(UTC).isoformat(),
                "artifact_format_version": 1,
                "source_sha256": source_hash,
                "configuration_hash": config_hash,
                "code_version": code_version,
                "working_tree_dirty": working_tree_dirty,
                "run_configuration": run_config,
                "evaluation_folds": [
                    f"validation_{origin.date().isoformat()}" for origin in origins
                ]
                + ["final_test"],
                "selection_cutoff": str(selection_cutoff.date()),
                "forecast_origin": str(forecast_origin.date()),
                "training_cutoff": str(forecast_origin.date()),
                "test_start": str(test_start.date()),
                "products": len(cohort),
                "forecast_products": len({r["product_id"] for r in forecasts}),
                "sparse_products_in_cohort": int(
                    sum(
                        ranked.loc[sku, "zero_share"] >= 0.5
                        for sku in cohort
                        if sku in ranked.index
                    )
                ),
                "product_code_map": {str(k): v for k, v in product_codes.items()},
                "cohort_definition": "Selected before validation from an initial training-only window: up to 39 high-volume eligible products plus the most intermittent eligible product; eligibility requires 8 complete weeks and positive units. Forecasts require activity through the common origin.",
                "weeks": period,
                "features": FEATURES,
                "feature_schema": {
                    name: ("categorical" if name == "product_code" else "numeric")
                    for name in FEATURES
                },
                "model": "LightGBM pooled direct multi-horizon",
                "model_configuration": model_config,
                "target_transform": "log1p" if use_log_target else "identity",
                "validation_target_comparison": {
                    "identity": raw_validation,
                    "log1p": log_validation,
                    "selected": "log1p" if use_log_target else "identity",
                },
                "validation_metrics": metrics(val_actual, val_pred),
                "selected_baseline": baseline_labels[selected_baseline_key],
                "validation_baselines": baseline_validation,
                "interval_calibration": {
                    "method": "absolute validation residuals with finite-sample conformal-style quantiles",
                    "samples": len(val_actual),
                    "global_samples": len(residuals),
                    "horizons": calibration_by_horizon,
                },
                "metrics": holdout_metrics,
                "feature_importance": sorted(
                    [
                        {"name": n, "gain": float(v)}
                        for n, v in zip(
                            FEATURES, model.booster_.feature_importance(importance_type="gain")
                        )
                    ],
                    key=lambda x: x["gain"],
                    reverse=True,
                ),
            },
            indent=2,
            default=str,
            allow_nan=False,
        )
    )
    return {
        "quality": quality,
        "metadata": json.loads((out / "metadata.json").read_text()),
        "forecast_count": len(forecasts),
        "backtest_count": len(validation_backtests) + len(bt),
    }
