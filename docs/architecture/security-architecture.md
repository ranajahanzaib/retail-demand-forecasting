# Security Architecture & Threat Model

Summarizes trust boundaries, input validation, and deserialization safety for Retail Demand Forecasting.

## Local-First Threat Model

The application operates as a **local-first analytical tool** with a single operator on `localhost`:

```
[Raw Files: .xlsx / .csv]
          │
          ▼ (Validation: load_transactions & prepare_transactions)
[Python Core Engine]
          │
          ▼ (Local Disk: artifacts/)
[FastAPI Endpoints] ──(Loopback:8000)──> [Vite Proxy:5173] ──> [Browser Client]
```

## Security Controls

1. **Input Validation:**
   * **CLI:** Checks file existence and read permissions.
   * **Pipeline:** Strips non-numeric values, enforces schemas, and validates numeric finiteness to prevent overflow.
   * **FastAPI / Pydantic:** The simulation endpoint strictly validates bounds (`adjustment_pct` between $-50$ and $+100$, `window_weeks` $\in \{2, 4, 8\}$, `shock_type` $\in \{\text{"sustained"}, \text{"one-time"}\}$), returning 422 on invalid inputs.
2. **Joblib / Pickle Safety:**
   * `joblib.load()` executes arbitrary Python bytecode during deserialization. The model file (`model.joblib`) must only be loaded if generated locally or received from a verified, trusted source.
3. **Privacy & Secrets:**
   * `CustomerID` is dropped during weekly aggregation and is never stored in Parquet or exposed via the API.
   * No API keys, credentials, or cloud secrets are used or committed to the repository.
