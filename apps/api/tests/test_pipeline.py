import json
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from demandsense import api
from demandsense.pipeline import (
    baseline,
    examples_through_cutoff,
    finite_sample_quantile,
    load_transactions,
    make_features,
    metrics,
    prepare_transactions,
    run_pipeline,
    select_product_cohort,
    validation_origins,
    weekly_series,
)


def transactions():
    return pd.DataFrame(
        [
            {
                "InvoiceNo": "1",
                "StockCode": "A",
                "Description": "item",
                "Quantity": 2,
                "InvoiceDate": "2011-01-04",
                "UnitPrice": 3,
                "CustomerID": None,
                "Country": "UK",
            },
            {
                "InvoiceNo": "c2",
                "StockCode": "A",
                "Description": "item",
                "Quantity": -2,
                "InvoiceDate": "2011-01-05",
                "UnitPrice": 3,
                "CustomerID": None,
                "Country": "UK",
            },
            {
                "InvoiceNo": "3",
                "StockCode": "M",
                "Description": "manual",
                "Quantity": 1,
                "InvoiceDate": "2011-01-05",
                "UnitPrice": 4,
                "CustomerID": None,
                "Country": "UK",
            },
            {
                "InvoiceNo": "4",
                "StockCode": "B",
                "Description": "bad",
                "Quantity": 1,
                "InvoiceDate": "not a date",
                "UnitPrice": 2,
                "CustomerID": None,
                "Country": "UK",
            },
            {
                "InvoiceNo": "1",
                "StockCode": "A",
                "Description": "item",
                "Quantity": 2,
                "InvoiceDate": "2011-01-04",
                "UnitPrice": 3,
                "CustomerID": None,
                "Country": "UK",
            },
            {
                "InvoiceNo": "5",
                "StockCode": "A",
                "Description": "return",
                "Quantity": -3,
                "InvoiceDate": "2011-01-06",
                "UnitPrice": 3,
                "CustomerID": None,
                "Country": "UK",
            },
            {
                "InvoiceNo": "6",
                "StockCode": "C",
                "Description": "free",
                "Quantity": 1,
                "InvoiceDate": "2011-01-06",
                "UnitPrice": 0,
                "CustomerID": None,
                "Country": "UK",
            },
            {
                "InvoiceNo": "7",
                "StockCode": "D",
                "Description": "zero",
                "Quantity": 0,
                "InvoiceDate": "2011-01-06",
                "UnitPrice": 2,
                "CustomerID": None,
                "Country": "UK",
            },
            {
                "InvoiceNo": "8",
                "StockCode": None,
                "Description": "missing sku",
                "Quantity": 1,
                "InvoiceDate": "2011-01-06",
                "UnitPrice": 2,
                "CustomerID": None,
                "Country": "UK",
            },
            {
                "InvoiceNo": "9",
                "StockCode": "E",
                "Description": None,
                "Quantity": 1,
                "InvoiceDate": "2011-01-06",
                "UnitPrice": 2,
                "CustomerID": None,
                "Country": "UK",
            },
        ]
    )


def test_cleaning_reports_exclusions_and_keeps_missing_customer():
    accepted, report = prepare_transactions(transactions())
    assert list(accepted.StockCode) == ["A", "A", "E"]
    assert report["excluded_rows"] == 7
    assert report["cancellation_rows"] == 1
    assert report["administrative_rows"] == 1
    assert report["invalid_date_rows"] == 1
    assert report["invalid_quantity_rows"] == 3
    assert report["invalid_price_rows"] == 1
    assert report["missing_product_id_rows"] == 1
    assert report["duplicate_candidates"] == 2
    assert report["transformed_description_rows"] == 1
    assert report["missing_customer_ids"] == 10


def test_cleaning_rejects_missing_invoice_ids_and_nonfinite_numeric_values():
    frame = pd.DataFrame(
        [
            {
                "InvoiceNo": "1",
                "StockCode": "A",
                "Description": "item",
                "Quantity": 1,
                "InvoiceDate": "2011-01-03",
                "UnitPrice": 2,
                "CustomerID": None,
                "Country": "UK",
            },
            {
                "InvoiceNo": " ",
                "StockCode": "B",
                "Description": "item",
                "Quantity": 1,
                "InvoiceDate": "2011-01-03",
                "UnitPrice": 2,
                "CustomerID": None,
                "Country": "UK",
            },
            {
                "InvoiceNo": "3",
                "StockCode": "C",
                "Description": "item",
                "Quantity": float("inf"),
                "InvoiceDate": "2011-01-03",
                "UnitPrice": 2,
                "CustomerID": None,
                "Country": "UK",
            },
            {
                "InvoiceNo": "4",
                "StockCode": "D",
                "Description": "item",
                "Quantity": 1,
                "InvoiceDate": "2011-01-03",
                "UnitPrice": float("inf"),
                "CustomerID": None,
                "Country": "UK",
            },
        ]
    )
    accepted, report = prepare_transactions(frame)
    assert accepted.StockCode.tolist() == ["A"]
    assert report["missing_invoice_id_rows"] == 1
    assert report["nonfinite_quantity_rows"] == 1
    assert report["invalid_price_rows"] == 1


def test_dates_parse_iso_and_uci_day_first_formats_without_date_inference_leak():
    frame = transactions().iloc[[0]].copy()
    frame["InvoiceDate"] = ["2011-01-04"]
    iso, _ = prepare_transactions(frame)
    frame["InvoiceDate"] = ["04/01/2011 08:26"]
    uci, _ = prepare_transactions(frame)
    assert iso.InvoiceDate.iloc[0] == pd.Timestamp("2011-01-04")
    assert uci.InvoiceDate.iloc[0] == pd.Timestamp("2011-01-04 08:26")


def test_features_only_read_history_and_target_calendar():
    origin = pd.Timestamp("2020-01-06")
    target = pd.Timestamp("2020-01-13")
    dates = pd.date_range(end=target, periods=9, freq="7D")
    before = make_features(pd.Series(range(1, 9), index=dates[:8]), origin, target, 1)
    after = make_features(
        pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 90000], index=dates), origin, target, 1
    )
    assert before["lag_1"] == 8
    assert before["mean_4"] == 6.5
    assert before == after


def test_baselines_and_metrics():
    hist = np.array([1.0, 2.0, 3.0, 4.0])
    assert baseline(hist, 1, "naive") == 4
    assert baseline(hist, 2, "mean4") == 2.5
    assert baseline(hist, 1, "repeat4") == 1
    assert metrics([1, 3], [2, 2])["mae"] == 1
    assert metrics([1, 3], [2, 2])["wape_percent"] == 50
    assert metrics([1], [2])["bias"] == 1
    assert metrics([0], [2])["wape"] is None
    assert metrics([0], [2])["wape_unavailable_reason"]


def test_training_labels_respect_each_fold_cutoff():
    examples = [
        ("features-a", pd.Timestamp("2020-01-06"), 1),
        ("features-b", pd.Timestamp("2020-01-13"), 2),
        ("features-c", pd.Timestamp("2020-01-20"), 3),
    ]
    eligible = examples_through_cutoff(examples, pd.Timestamp("2020-01-13"))
    assert [row[1] for row in eligible] == [pd.Timestamp("2020-01-06"), pd.Timestamp("2020-01-13")]


def test_validation_origins_keep_all_four_targets_before_final_holdout():
    weeks = list(pd.date_range("2020-01-06", periods=20, freq="7D"))
    test_start = weeks[-4]
    origins = validation_origins(weeks, weeks[8], test_start)
    assert origins
    assert all(origin + pd.Timedelta(days=28) < test_start for origin in origins)
    assert all(origin + pd.Timedelta(days=35) >= test_start for origin in [origins[-1]])


def test_finite_sample_quantile_uses_corrected_order_statistic():
    assert finite_sample_quantile([1, 2, 3], 0.5) == 2
    assert finite_sample_quantile([1, 2, 3], 0.8) == 3
    assert finite_sample_quantile([], 0.8) is None


def test_product_selection_is_frozen_before_later_volume_changes():
    rows = []
    weeks = pd.date_range("2020-01-06", periods=30, freq="7D")
    for index in range(45):
        for pos, week in enumerate(weeks):
            units = (index + 1) if pos < 26 else (1_000_000 if index == 0 else 1)
            rows.append(
                {"StockCode": f"SKU-{index:03d}", "week_start": week, "weekly_units_sold": units}
            )
    frame = pd.DataFrame(rows)
    cutoff = weeks[26]
    cohort, _ = select_product_cohort(frame, cutoff)
    changed = frame.copy()
    changed.loc[
        (changed.StockCode == "SKU-000") & (changed.week_start >= cutoff), "weekly_units_sold"
    ] = 1_000_000_000
    cohort_after, _ = select_product_cohort(changed, cutoff)
    assert cohort == cohort_after
    assert "SKU-000" not in cohort


def test_product_selection_keeps_the_most_intermittent_eligible_sku():
    rows = []
    weeks = pd.date_range("2020-01-06", periods=10, freq="7D")
    levels = {
        "A": [10] * 10,
        "B": [9] * 10,
        "C": [8] * 10,
        "D": [7, 7, 7, 7, 7, 7, 7, 0, 0, 0],
        "E": [6, 6, 0, 0, 0, 0, 0, 0, 0, 0],
        "F": [5, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    }
    for sku, values in levels.items():
        rows.extend(
            {"StockCode": sku, "week_start": week, "weekly_units_sold": units}
            for week, units in zip(weeks, values)
        )
    cohort, _ = select_product_cohort(pd.DataFrame(rows), weeks[-1], maximum=4)
    assert cohort == ["A", "B", "C", "F"]


def test_synthetic_demo_runs_end_to_end_and_labels_its_data_mode(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[3]
    fixture = root / "data" / "demo" / "transactions.csv"
    result = run_pipeline(
        load_transactions(fixture), tmp_path, data_mode="synthetic demo fixture (not UCI)"
    )
    metadata = json.loads((tmp_path / "metadata.json").read_text())
    manifest = json.loads((tmp_path / "dataset-manifest.json").read_text())
    assert result["forecast_count"] > 0
    assert result["backtest_count"] > result["forecast_count"]
    assert metadata["data_mode"] == "synthetic demo fixture (not UCI)"
    assert manifest["dataset_doi"] is None
    assert (tmp_path / "model.joblib").exists()
    monkeypatch.setattr(api, "ARTIFACTS", tmp_path)
    client = TestClient(api.app)
    assert client.get("/api/health").json()["artifacts_available"] is True
    assert client.get("/api/metadata").json()["data_mode"] == "synthetic demo fixture (not UCI)"
    assert client.get("/api/dataset/summary").status_code == 200
    assert client.get("/api/dataset/quality").status_code == 200
    assert client.get("/api/dataset/manifest").status_code == 200
    assert client.get("/api/products?limit=10").status_code == 200
    assert client.get("/api/products?limit=0").status_code == 422
    assert client.get("/api/forecasts").status_code == 200
    product_id = json.loads((tmp_path / "forecasts.json").read_text())[0]["product_id"]
    assert client.get(f"/api/products/{product_id}").status_code == 200
    assert client.get(f"/api/products/{product_id}/history").status_code == 200
    assert client.get(f"/api/forecasts/{product_id}").status_code == 200
    assert client.get(f"/api/forecasts/{product_id}/comparison").status_code == 200
    assert client.get("/api/models").status_code == 200
    assert client.get("/api/models/metrics").status_code == 200
    assert client.get("/api/models/metrics/by-horizon").status_code == 200
    assert client.get("/api/models/metrics/by-product").status_code == 200
    assert client.get("/api/backtests").status_code == 200
    assert client.get(f"/api/backtests/{product_id}").status_code == 200
    assert client.get("/api/intervals/coverage").json()["count"] > 0
    assert client.get("/api/features/importance").status_code == 200
    scenario = client.post(
        "/api/simulations/demand-shift",
        json={
            "product_id": product_id,
            "adjustment_pct": 0,
            "window_weeks": 4,
            "shock_type": "sustained",
        },
    )
    assert scenario.status_code == 200
    assert all(row["change_units"] == 0 for row in scenario.json()["items"])
    original_weekly = pd.read_parquet(tmp_path / "weekly.parquet")
    shifted = client.post(
        "/api/simulations/demand-shift",
        json={
            "product_id": product_id,
            "adjustment_pct": 30,
            "window_weeks": 4,
            "shock_type": "sustained",
        },
    ).json()
    shifted_again = client.post(
        "/api/simulations/demand-shift",
        json={
            "product_id": product_id,
            "adjustment_pct": 30,
            "window_weeks": 4,
            "shock_type": "sustained",
        },
    ).json()
    assert shifted["items"] == shifted_again["items"]
    assert shifted["changed_features"]
    assert pd.read_parquet(tmp_path / "weekly.parquet").equals(original_weekly)
    assert (
        client.post(
            "/api/simulations/demand-shift",
            json={
                "product_id": product_id,
                "adjustment_pct": 10,
                "window_weeks": 3,
                "shock_type": "sustained",
            },
        ).status_code
        == 422
    )


def test_weekly_series_excludes_partial_boundary_and_aggregates_units():
    frame = pd.DataFrame(
        [
            {
                "InvoiceNo": "1",
                "StockCode": "A",
                "Description": "item",
                "Quantity": 99,
                "InvoiceDate": "2011-01-05",
                "UnitPrice": 2,
                "CustomerID": None,
                "Country": "UK",
            },
            {
                "InvoiceNo": "2",
                "StockCode": "A",
                "Description": "item",
                "Quantity": 2,
                "InvoiceDate": "2011-01-12",
                "UnitPrice": 2,
                "CustomerID": None,
                "Country": "UK",
            },
            {
                "InvoiceNo": "3",
                "StockCode": "A",
                "Description": "item",
                "Quantity": 3,
                "InvoiceDate": "2011-01-16",
                "UnitPrice": 2,
                "CustomerID": None,
                "Country": "UK",
            },
            {
                "InvoiceNo": "4",
                "StockCode": "A",
                "Description": "item",
                "Quantity": 4,
                "InvoiceDate": "2011-01-17",
                "UnitPrice": 2,
                "CustomerID": None,
                "Country": "UK",
            },
        ]
    )
    accepted, _ = prepare_transactions(frame)
    weekly, window = weekly_series(accepted)
    assert weekly.week_start.min() == pd.Timestamp("2011-01-10")
    assert weekly.iloc[0].weekly_units_sold == 5
    assert window["complete_week_start"] == "2011-01-10"


def test_product_week_calendar_fills_internal_gaps_but_stops_at_last_sale():
    rows = []
    for invoice, sku, quantity, day in [
        ("1", "A", 2, "2011-01-03"),
        ("2", "A", 1, "2011-01-23"),
        ("3", "B", 1, "2011-02-06"),
    ]:
        rows.append(
            {
                "InvoiceNo": invoice,
                "StockCode": sku,
                "Description": sku,
                "Quantity": quantity,
                "InvoiceDate": day,
                "UnitPrice": 2,
                "CustomerID": None,
                "Country": "UK",
            }
        )
    accepted, _ = prepare_transactions(pd.DataFrame(rows))
    weekly, _ = weekly_series(accepted)
    a = weekly[weekly.StockCode == "A"].sort_values("week_start")
    assert a.weekly_units_sold.tolist() == [2, 0, 1]
    assert a.week_start.max() == pd.Timestamp("2011-01-17")
