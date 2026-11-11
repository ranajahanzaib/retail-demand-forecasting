# Architecture

`apps/api/src/demandsense/pipeline.py` owns transaction validation, cleaning, aggregation, feature construction, baselines, rolling validation, final fitting, and local artifact writing. `cli.py` exposes the full pipeline, synthetic demo generation, and artifact inspection. `api.py` reads persisted artifacts and validates scenario requests; ordinary requests do not retrain. The Vite React client uses the API through its development proxy and TanStack Query for fetching.

Artifacts are local files under `artifacts/`: a trusted `joblib` model, weekly Parquet data, JSON forecasts/backtests, quality report, data manifest, and model metadata. The original workbook is not committed. Python model artifacts are unsafe to load from an untrusted source.
