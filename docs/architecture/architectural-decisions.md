# Architectural Decision Records (ADRs)

Key architectural decisions and trade-offs in Retail Demand Forecasting.

---

### ADR 1: Direct Multi-Horizon vs. Recursive Autoregression
* **Decision:** Implement a **pooled direct multi-horizon regressor** where horizon $h \in \{1, 2, 3, 4\}$ is an explicit input feature.
* **Rationale:** Eliminates compounding prediction error across multiple steps and guarantees that horizon +4 features depend strictly on data known at origin.

### ADR 2: Pooled LightGBM vs. Per-SKU Classical Models
* **Decision:** Train a single pooled LightGBM model across all products using `product_code` as a categorical feature.
* **Rationale:** Shares statistical strength across items (benefiting intermittent or short-history products) and trains in $<1\text{s}$ on commodity CPUs without GPU dependencies.

### ADR 3: File-Artifact Persistence vs. Database Service
* **Decision:** Store all tabular data and model weights in `artifacts/` as `.parquet`, `.joblib`, and `.json`.
* **Rationale:** Provides zero-friction local installation without requiring users to install, configure, or migrate a database server.

### ADR 4: Conformal-Style Residual Quantiles vs. Parametric Intervals
* **Decision:** Derive 80% and 90% prediction intervals from pre-test validation residual order statistics.
* **Rationale:** Retail demand errors are heavily skewed and heteroskedastic; empirical quantiles provide honest coverage estimates without assuming Gaussian distributions.

### ADR 5: In-Span Zero Filling vs. Global Calendar Extension
* **Decision:** Fill zero sales only between each product's first and last observed sale.
* **Rationale:** Prevents models from penalizing products for zero sales before product introduction or hallucinating death spirals after product retirement.
