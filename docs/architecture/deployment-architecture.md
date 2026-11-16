# Deployment Architecture & Environment Topology

Details the local-first multi-process topology, network configuration, and CI workflows.

```mermaid
flowchart TB
    subgraph Host["Host Operating System"]
        subgraph Filesystem["Local Workspace Filesystem"]
            Data["data/raw/ & data/demo/<br/>Source Workbooks & CSVs"]
            Artifacts["artifacts/ or artifacts/demo/<br/>model.joblib, weekly.parquet, *.json"]
        end

        subgraph Backend["Backend Process (Python 3.12+ / uv)"]
            FastAPI["Uvicorn ASGI Server<br/>Port: 8000 (Default)"]
            CLIProc["CLI Subprocess (Ad-Hoc / Make)<br/>demandsense pipeline"]
        end

        subgraph Frontend["Frontend Process (Node.js 20+ / pnpm)"]
            Vite["Vite Dev Server<br/>Port: 5173 (Host: 0.0.0.0)<br/>Proxy: /api -> http://localhost:8000"]
        end

        subgraph Browser["Client Environment"]
            Web["Web Browser / Playwright<br/>http://localhost:5173"]
        end
    end

    Data -->|"Read by batch CLI"| CLIProc
    CLIProc -->|"Writes artifacts"| Artifacts
    Artifacts -->|"Read by server"| FastAPI

    Web -->|"HTTP (Port 5173)"| Vite
    Vite -->|"Reverse proxy /api/*"| FastAPI
```

## Runtime Configuration

* **Backend API:** FastAPI running under Uvicorn on `http://localhost:8000`. Configured via `RETAIL_DEMAND_FORECASTING_ARTIFACTS` (defaults to `artifacts/`).
* **Frontend Web:** Vite development server running on `http://localhost:5173`. Proxies `/api` calls to `http://localhost:8000` to prevent CORS issues. Production assets build to `apps/web/dist/`.
* **CI Workflow (`.github/workflows/ci.yml`):**
  * `python`: Runs `ruff check` and `pytest`.
  * `frontend`: Builds demo artifacts using the synthetic fixture, builds the React app, lints, runs unit tests, and executes Playwright end-to-end tests on Chromium.
