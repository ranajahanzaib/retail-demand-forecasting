# Architecture Overview

Retail Demand Forecasting is a **local-first retail forecasting and model reliability laboratory**. It turns raw transaction records into weekly product demand forecasts, benchmarks LightGBM against simple baselines, and exposes predictions and real-time sensitivity simulations through a FastAPI backend and React dashboard.

```mermaid
flowchart LR
    subgraph Ingestion["1. Ingestion & Preprocessing"]
        Raw["Raw Transactions<br/>(.xlsx / .csv)"] --> Prep["prepare_transactions()<br/>Cleaning & Audit"]
        Prep --> Weekly["weekly_series()<br/>Mon–Sun Resampling"]
    end

    subgraph Modeling["2. Batch Modeling & Evaluation"]
        Weekly --> Cohort["select_product_cohort()<br/>Freeze Top 39 + 1 Intermittent"]
        Cohort --> Feat["make_features()<br/>18 Origin-Bounded Features"]
        Feat --> Val["Rolling Validation<br/>Fold Tuning & Baseline Select"]
        Val --> Fit["Final LightGBM Fit<br/>Direct h=1..4"]
        Val --> Calib["Residual Calibration<br/>Finite-Sample 80%/90%"]
        Fit & Calib --> Holdout["Untouched Final Holdout<br/>4-Week Holdout vs Baselines"]
    end

    subgraph Storage["3. Local Artifact Repository"]
        Weekly --> Parquet["weekly.parquet"]
        Fit --> Model["model.joblib"]
        Holdout --> Forecasts["forecasts.json"]
        Holdout --> Backtests["backtests.json"]
        Holdout --> Metadata["metadata.json"]
        Prep --> Quality["quality.json"]
    end

    subgraph Serving["4. Serving API (FastAPI)"]
        Parquet & Forecasts & Backtests & Metadata & Quality --> Endpoints["FastAPI Endpoints<br/>/api/products, /api/forecasts, etc."]
        Model & Parquet --> SimEngine["Demand Shift Simulator<br/>POST /api/simulations/demand-shift"]
    end

    subgraph UI["5. Frontend (React 19 SPA)"]
        Endpoints --> TanStack["TanStack Query Cache"]
        SimEngine --> TanStack
        TanStack --> Dashboard["React Dashboard<br/>Recharts Forecasts & Diagnostics"]
    end
```

## Key Architectural Principles

1. **Decoupled Batch & Serving:** Heavy data cleaning, rolling validation, and model fitting run offline via the CLI. Serving is lightweight and reads static artifacts from disk.
2. **Zero-Database (File-Artifacts):** Inter-tier communication is mediated by immutable local files in `artifacts/` (`.parquet`, `.joblib`, `.json`), requiring zero external database or cache services.
3. **Direct Multi-Horizon Modeling:** A single pooled LightGBM model forecasts horizons $1 \dots 4$ directly, avoiding recursive error compounding.
4. **Honest Benchmarking:** Compares LightGBM against three simple baselines (*Last Observation*, *Trailing 4-Week Mean*, *4-Week Repeating Pattern*) on an untouched 4-week holdout.
5. **Conformal-Style Residual Bounds:** Prediction intervals are calibrated on validation residuals using finite-sample order statistics rather than assuming Gaussian distributions.

## Architecture Documents

* **[system-context.md](system-context.md)** — External actors, boundaries, and data sources.
* **[high-level-architecture.md](high-level-architecture.md)** — Core subsystems and responsibilities.
* **[component-architecture.md](component-architecture.md)** — Module breakdown across CLI, pipeline, API, and UI.
* **[data-architecture.md](data-architecture.md)** — Data flow, schemas, and 18-feature registry.
* **[execution-flows.md](execution-flows.md)** — Batch training and real-time simulation lifecycles.
* **[deployment-architecture.md](deployment-architecture.md)** — Local processes, network proxying, and CI.
* **[reliability-and-failure-handling.md](reliability-and-failure-handling.md)** — Edge case handling and state transitions.
* **[security-architecture.md](security-architecture.md)** — Threat boundaries, input validation, and Joblib safety.
* **[architectural-decisions.md](architectural-decisions.md)** — Key ADR trade-offs and rationale.
* **[architecture-gaps.md](architecture-gaps.md)** — Known production and scalability limitations.
