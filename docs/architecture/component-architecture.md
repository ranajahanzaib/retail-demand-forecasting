# Component Architecture

Details the internal modules, functions, and interfaces across the backend and frontend.

```mermaid
flowchart TB
    subgraph APIService["Backend Application (apps/api / demandsense)"]
        subgraph CLIModule["demandsense.cli"]
            CLI_App["Typer app instance"]
            CmdPipeline["pipeline(input, output, data_mode)"]
            CmdDemo["build_demo(input, output)"]
            CmdInspect["inspect(artifacts)"]
            CLI_App --> CmdPipeline
            CLI_App --> CmdDemo
            CLI_App --> CmdInspect
        end

        subgraph PipelineModule["demandsense.pipeline"]
            LoadTx["load_transactions()"]
            PrepTx["prepare_transactions()"]
            WeeklySeries["weekly_series()"]
            CohortSelect["select_product_cohort()"]
            MakeFeats["make_features()"]
            Baselines["baseline()"]
            QuantileCalc["finite_sample_quantile()"]
            RunPipeline["run_pipeline()"]

            RunPipeline --> LoadTx & PrepTx & WeeklySeries & CohortSelect & MakeFeats & Baselines & QuantileCalc
        end

        subgraph ServerModule["demandsense.api"]
            FastAPI_App["FastAPI app (demandsense.api:app)"]
            Endpoints["GET /api/health, /api/metadata, /api/products,<br/>/api/forecasts, /api/models/metrics, /api/backtests"]
            SimulateEp["POST /api/simulations/demand-shift"]

            FastAPI_App --> Endpoints & SimulateEp
            SimulateEp --> MakeFeats
        end
    end

    subgraph ClientService["Frontend Application (apps/web)"]
        AppShell["App.tsx Shell"]
        TanStackQueries["TanStack Query Cache"]
        Views["Overview, Products, Comparison,<br/>Backtests, Reliability, Quality"]

        AppShell --> TanStackQueries --> Views
    end

    CmdPipeline --> RunPipeline
    CmdDemo --> RunPipeline
    TanStackQueries -->|"REST HTTP JSON"| FastAPI_App
```

## Module Responsibilities

### Backend (`apps/api`)
* **`demandsense.cli`:** Typer CLI commands:
  * `pipeline`: Runs full ingestion, training, evaluation, and artifact generation on arbitrary datasets.
  * `build-demo`: Quick-start command running the pipeline on the bundled synthetic fixture.
  * `inspect`: Prints run metadata and quality audits.
* **`demandsense.pipeline`:** Core analytical engine:
  * `load_transactions()` / `prepare_transactions()`: Ingestion and conservative cleaning.
  * `weekly_series()`: Monday–Sunday aggregation, boundary week trimming, in-span zero filling.
  * `select_product_cohort()`: Freezes cohort based strictly on pre-test window.
  * `make_features()`: Extracts 18 origin-bounded features (lags, rolling means, volatility, calendar).
  * `finite_sample_quantile()`: Conformal-style order statistics for prediction intervals.
  * `baseline()`: Implements *naive*, *mean4*, and *repeat4* baselines.
  * `run_pipeline()`: End-to-end orchestrator.
* **`demandsense.api`:** FastAPI endpoints providing read access to artifacts and on-the-fly scenario simulations via `POST /api/simulations/demand-shift`.

### Frontend (`apps/web`)
* **`App.tsx`:** Single-page dashboard shell managing tabs, state, and Recharts components.
* **`metrics.ts`:** Display formatting and empirical interval coverage calculations.
