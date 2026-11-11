# Forecasting methodology

## Target and time axis

The target is gross positive transaction quantity per SKU per Monday–Sunday complete week. Cancellations and nonpositive quantities do not contribute to target. Weeks before a SKU's first observation or after its final observation are not assumed to be zero. Dataset boundary weeks are omitted.

## Features and horizons

For horizon 1–4, a pooled regression row contains a stable product key, horizon, lagged values (1, 2, 3, 4, 8 weeks), trailing means and dispersion, zero-week count, weeks since positive sales, product age, and known target month/quarter. Every sales-derived feature is computed from observations no later than the forecast origin. Direct training labels occur at the corresponding future horizon; horizon +4 never uses actual values from horizons +1 to +3.

## Evaluation

The cohort is frozen from the initial half of complete weeks, before validation: up to 39 higher-volume eligible SKUs plus the most intermittent eligible SKU, each with at least eight complete observations and positive units. Validation origins occur after this selection cutoff. Products must have an observation row through the shared forecast origin to receive final forecasts; the pipeline does not append zero demand after a product's final sale. The last four complete weeks are reserved as a chronological holdout. MAE, aggregate WAPE and predicted-minus-actual bias are computed on common holdout rows for the ML and simple baselines. The strongest simple baseline is selected using validation performance. Calibration uses finite-sample absolute residual quantiles by horizon when at least 20 samples are available, with pooled fallback. Temporal dependence and drift mean intervals do not carry unconditional coverage guarantees.

## Demand simulation

The API perturbs the selected product's recent history and calls the same feature builder and frozen model. Reported differences are sensitivity under a hypothetical history. They have no known future outcomes and are not accuracy claims.
