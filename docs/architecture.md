# Architecture

`apps/api/src/demandsense/pipeline.py` owns transaction validation, cleaning, aggregation, feature construction, baselines, rolling validation, final fitting, and local artifact writing. `cli.py` exposes the full pipeline, synthetic demo generation, and artifact inspection. `api.py` reads persisted artifacts and validates scenario requests; ordinary requests do not retrain. The Vite React client uses the API through its development proxy and TanStack Query for fetching.

Artifacts are local files under `artifacts/`: a trusted `joblib` model, weekly Parquet data, JSON forecasts/backtests, quality report, data manifest, and model metadata. The original workbook is not committed. Python model artifacts are unsafe to load from an untrusted source.

---

## Detailed System Design & Architecture Package

For comprehensive architecture documentation, component breakdowns, data models, execution sequence diagrams, and failure analyses, see the **[Architecture Documentation Suite](architecture/README.md)**:

- **[System Context & Boundaries](architecture/system-context.md)** — External actors, raw inputs, and system boundary.
- **[High-Level Architecture](architecture/high-level-architecture.md)** — Core subsystems, boundaries, and communication patterns.
- **[Component Architecture](architecture/component-architecture.md)** — Detailed module breakdowns for `demandsense` and React.
- **[Data Architecture & Schemas](architecture/data-architecture.md)** — Tabular schemas, cleaning rules, and the 18-feature registry.
- **[Execution Flows & Lifecycles](architecture/execution-flows.md)** — Sequence diagrams for batch training and real-time simulation.
- **[Deployment Architecture](architecture/deployment-architecture.md)** — Local process boundaries, network proxying, and CI/CD pipelines.
- **[Reliability & Failure Handling](architecture/reliability-and-failure-handling.md)** — Defensive guards, edge cases, and state transitions.
- **[Security Architecture](architecture/security-architecture.md)** — Threat modeling, input validation, and Joblib safety.
- **[Architectural Decision Records (ADRs)](architecture/architectural-decisions.md)** — Six foundational design trade-offs evaluated.
- **[Architectural Gaps & Limitations](architecture/architecture-gaps.md)** — Production limitations and scalability boundaries.

Standalone Mermaid source diagrams are maintained under **[`docs/architecture/diagrams/`](architecture/diagrams/)**.
