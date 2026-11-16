# Architecture Gaps & Limitations

Known operational limitations and trade-offs in the current design.

1. **Repeated Disk I/O:** `api.py` reads `weekly.parquet` from disk on every historical query and re-loads `model.joblib` on every simulation request. Adding an in-memory lifespan cache would improve high-concurrency throughput.
2. **Fixed Cohort Cap (40 SKUs):** Product selection hardcodes a cap of 40 products (39 high-volume + 1 intermittent) for inspectability. Scaling to enterprise catalogs with 50,000+ SKUs requires configurable cohort partitioning.
3. **Symmetric Absolute Error Intervals:** The conformal engine calculates absolute residuals $|y - \hat{y}|$, producing symmetric bands clamped at zero. This does not model the long right-tail upside typical of wholesale spikes or viral retail demand.
4. **No Remote Triggering API:** Model training must be executed from the CLI (`demandsense pipeline`). There is no background worker queue (Celery/ARQ) to trigger or monitor retraining from the web UI.
5. **Data Censoring (Unobserved Lost Sales):** Gross positive transaction logs capture observed sales, not latent demand. The model cannot detect stockouts or unfulfilled demand without inventory balance data.
