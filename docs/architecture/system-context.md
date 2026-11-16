# System Context & Boundaries

Describes the boundaries of Retail Demand Forecasting, external actors, inputs, and environment integration.

```mermaid
flowchart TB
    subgraph External["External Actors & Data Sources"]
        User["Retail Analyst / Planner<br/>[Human Operator]"]
        UCI["UCI Online Retail Dataset<br/>[Optional Excel / CSV Source]"]
        DemoData["Synthetic Transaction Fixture<br/>[data/demo/transactions.csv]"]
    end

    subgraph SystemBoundary["Retail Demand Forecasting (Local-First Boundary)"]
        CLI["Typer CLI<br/>(demandsense)"]
        Pipeline["Batch ML Pipeline<br/>(LightGBM + Pandas)"]
        API["FastAPI REST Server<br/>(Port 8000)"]
        UI["React 19 Dashboard<br/>(Port 5173 via Vite Proxy)"]
        Storage[("Local Artifact Store<br/>Parquet, Joblib, JSON")]
    end

    User -->|"Runs CLI / pipeline"| CLI
    User -->|"Interacts with UI"| UI
    UCI -.->|"Manual input to data/raw/"| CLI
    DemoData -->|"Default offline fixture"| CLI

    CLI --> Pipeline
    Pipeline -->|"Writes artifacts"| Storage

    UI -->|"HTTP /api"| API
    API -->|"Reads artifacts & models"| Storage
```

## System Entities

* **Retail Analyst [Operator]:** Runs CLI commands (`pipeline`, `build-demo`, `inspect`) to process data and train models; uses the dashboard to inspect forecasts, evaluation metrics, and run scenario simulations.
* **Data Sources:** 
  * *UCI Online Retail Dataset:* Manual download placed at `data/raw/Online-Retail.xlsx` for real-data reproduction.
  * *Synthetic Demo Fixture:* Bundled offline CSV at `data/demo/transactions.csv` for immediate local exploration and CI testing.
* **Local-First Boundary:** Operates completely offline without external databases (PostgreSQL/MySQL), cloud microservices, or external network requests.
