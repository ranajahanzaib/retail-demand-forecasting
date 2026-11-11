# Feature registry and temporal contract

Every sales-derived value is calculated from history ending on or before its forecast origin. Target month and quarter are known at the time a forecast is issued.

| Feature                           | Type                    |                        Lookback | Inference availability | Missing policy                                           | Leakage risk |
| --------------------------------- | ----------------------- | ------------------------------: | ---------------------- | -------------------------------------------------------- | ------------ |
| product_code                      | categorical product key |                            none | yes for frozen cohort  | lexicographic cohort mapping persisted in model metadata | Low          |
| horizon                           | integer                 |                            none | yes                    | horizon 1–4                                              | Low          |
| lag_1, lag_2, lag_3, lag_4, lag_8 | numeric                 |                   specified lag | yes                    | zero when shorter history                                | Low          |
| mean_2, mean_4, mean_8            | numeric                 |                 trailing window | yes                    | zero without observations                                | Low          |
| std_4, max_4, min_4               | numeric                 |                      trailing 4 | yes                    | zero with fewer than two observations for std            | Low          |
| zero_weeks_8                      | integer                 |                      trailing 8 | yes                    | count available zero weeks                               | Low          |
| weeks_since_sale                  | integer                 | since most recent positive sale | yes                    | available history length if no positive sale             | Low          |
| age_weeks                         | integer                 |                 origin-relative | yes                    | weeks observed for product                               | Low          |
| target_month, target_quarter      | integer                 |                 target calendar | yes                    | not applicable                                           | Low          |

Direct training examples store a distinct origin and future label date. Example rows are eligible for a fold only when their label date is at or before that fold's training cutoff. The last four complete weeks remain outside fitting and baseline selection.
