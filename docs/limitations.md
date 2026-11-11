# Limitations

- Roughly one year of historical observations provides little support for annual seasonal claims.
- Gross positive transactions are a sales proxy, not unconstrained demand. Availability, lost sales, and stockouts are not observed.
- Product activity windows are inferred from observed sales; a product may have existed before first sale or remained available after last sale.
- Sparse products, new items, wholesale orders, returns, and distribution shifts can weaken forecasts.
- Feature importance shows model reliance and is not causal evidence.
- Empirical residual intervals can miss their nominal coverage when errors are dependent or the data shifts.
- Hypothetical demand simulations do not have ground truth and are not accuracy tests.
- Python joblib model files can execute code when loaded. Only load artifacts generated and trusted locally.
- The MVP does not integrate current inventory, pricing, external signals, or live transaction systems.
