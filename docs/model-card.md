# Model card

## Intended use

Exploration of short-horizon weekly gross positive sales forecasts for retail products. Not an automated replenishment decision system.

## Data and model

The intended real-data source is UCI Online Retail (Dec 2010–Dec 2011). The algorithm is a CPU LightGBM regressor pooled across products and explicit horizons 1–4. Product cohort selection is bounded to the pre-test period. Inputs are origin-bounded sales history, product key, horizon, and known calendar fields.

## Evaluation

Chronological four-week final holdout. Generated run metadata records measured test metrics; this document makes no performance claim in advance. Baselines use the same products and test observations.

## Risks

Observed sales are not unconstrained demand. Short data history, unknown availability, sparse products, wholesale spikes, and distribution shift can impair accuracy. Prediction intervals are residual-calibrated estimates, not confidence intervals or guarantees. Model feature importance is not causal.
