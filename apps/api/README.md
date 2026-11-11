# Retail Demand Forecasting API

The Retail Demand Forecasting API provides local forecasting, evaluation, data quality, and
demand scenario endpoints for the bundled retail forecasting project.

For installation and full project usage, see the [project README](../../README.md).
The API requires Python 3.12 or later. Run it from this directory with:

```bash
uv sync
uv run uvicorn demandsense.main:app --reload
```

The installable Python distribution is `retail-demand-forecasting`. Its `demandsense` Python module and `demandsense` CLI command are retained as stable import and command names.

The interactive API reference is available at `http://localhost:8000/docs` while
the server is running. Forecast artifacts must be built before serving them.
