# Execution Flows & Runtime Lifecycles

Traces the primary execution paths across the batch training pipeline and online simulation.

---

## 1. Batch Pipeline Execution Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as Operator / Engineer
    participant CLI as demandsense.cli
    participant Pipe as demandsense.pipeline
    participant Disk as Local Artifact Storage

    User->>CLI: demandsense pipeline
    activate CLI
    CLI->>Pipe: load_transactions()
    CLI->>Pipe: run_pipeline()
    activate Pipe

    Pipe->>Pipe: prepare_transactions() (Clean & audit)
    Pipe->>Pipe: weekly_series() (Mon–Sun resample, in-span zero fill)
    Pipe->>Pipe: select_product_cohort() (Top 39 volume + 1 intermittent)
    Pipe->>Pipe: make_features() (18 origin-bounded features)

    loop Rolling Validation Origins
        Pipe->>Pipe: Fit fold models & evaluate baselines
    end

    Pipe->>Pipe: Select target transform (identity vs log1p) & best baseline
    Pipe->>Pipe: Calibrate empirical 80% & 90% error quantiles
    Pipe->>Pipe: Fit final LightGBM model on pre-test data
    Pipe->>Pipe: Predict untouched 4-week holdout & score MAE/WAPE/Bias

    Pipe->>Disk: Write weekly.parquet, model.joblib, and JSON manifests
    deactivate Pipe
    CLI->>User: Display run summary
    deactivate CLI
```

---

## 2. Demand-Shift Scenario Simulation Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as Dashboard User
    participant UI as React UI (App.tsx)
    participant API as FastAPI (api.py)
    participant Disk as Artifact Store
    participant ML as Frozen LightGBM Model

    User->>UI: Adjusts slider (+30% demand, 4-week window)
    UI->>API: POST /api/simulations/demand-shift
    activate API

    API->>API: Validate input (-50% to +100%, active product check)
    API->>Disk: Load weekly.parquet and model.joblib
    API->>API: Multiply recent history by shock factor (1 + pct/100)

    loop Horizons 1 to 4
        API->>API: Recompute 18 features from perturbed history
        API->>ML: Predict with frozen model
    end

    API->>API: Detect features outside historical [P05, P95] range
    API-->>UI: Return original vs simulated units & out-of-range flags
    deactivate API

    UI->>UI: Render dashed scenario line and unit delta
```
