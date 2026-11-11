# API

Start the API from `apps/api` with `uv run uvicorn demandsense.main:app --reload`. OpenAPI documentation is available at <http://localhost:8000/docs>.

## Routes

| Method and path                              | Purpose                                                         |
| -------------------------------------------- | --------------------------------------------------------------- |
| `GET /api/health`                            | API and artifact availability                                   |
| `GET /api/metadata`                          | Data mode, model configuration, cutoffs, and evaluation results |
| `GET /api/dataset/summary`                   | Dataset period and product counts                               |
| `GET /api/dataset/quality`                   | Ingestion and cleaning audit                                    |
| `GET /api/dataset/manifest`                  | Source and run provenance                                       |
| `GET /api/products?q=&limit=50&offset=0`     | Searchable, paginated forecastable products                     |
| `GET /api/products/{product_id}`             | Product details and activity status                             |
| `GET /api/products/{product_id}/history`     | Observed history through the forecast origin                    |
| `GET /api/forecasts`                         | Four-week forecasts for the frozen cohort                       |
| `GET /api/forecasts/{product_id}`            | One product's forecasts                                         |
| `GET /api/forecasts/{product_id}/comparison` | One product's model and baseline forecasts                      |
| `GET /api/models`                            | Model and baseline names                                        |
| `GET /api/models/metrics`                    | Holdout metrics and baseline comparison                         |
| `GET /api/models/metrics/by-horizon`         | Holdout metrics by forecast horizon                             |
| `GET /api/models/metrics/by-product`         | Holdout metrics by product                                      |
| `GET /api/backtests`                         | Rolling validation and final holdout records                    |
| `GET /api/backtests/{product_id}`            | Backtest records for one product                                |
| `GET /api/intervals/coverage`                | Empirical holdout coverage and interval widths                  |
| `GET /api/features/importance`               | Gain-based feature importance                                   |
| `POST /api/simulations/demand-shift`         | Recompute a hypothetical forecast after changing recent history |

Product listing accepts `limit` from 1 to 200 and a nonnegative `offset`. Requests that require unavailable artifacts return HTTP 503 with an explanation. Unknown products or forecasts return HTTP 404. The simulation validates its adjustment, window, and shock profile and returns HTTP 422 for invalid values.

## Demand-shift request

```json
{
  "product_id": "85123A",
  "adjustment_pct": 30,
  "window_weeks": 4,
  "shock_type": "sustained"
}
```

`adjustment_pct` ranges from -50 to 100. `window_weeks` accepts 2, 4, or 8. `shock_type` accepts `sustained` or `one-time`. The response contains original and simulated weekly point forecasts, the changed features, and an explicit note that hypothetical scenarios have no measured accuracy or coverage.

The API reads artifacts from `artifacts/` by default. Set `RETAIL_DEMAND_FORECASTING_ARTIFACTS` in the API process environment to use another directory. It does not retrain during dashboard requests or simulations.
